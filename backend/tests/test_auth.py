from datetime import datetime, timedelta, timezone

import jwt
import pytest
from sqlalchemy import select

from app.config import settings
from app.models import Document, RefreshToken, SearchEvent, User
from app.search.engine import SearchEngine
from app.search.loader import build_engine
from app.security import hash_refresh_token
from tests.conftest import ADMIN_EMAIL, PASSWORD, USER_EMAIL

PROTECTED = "/search/suggest?prefix=kaf"


def register(client, email="new@test.dev", password=PASSWORD, name="New User"):
    return client.post("/auth/register", json={"name": name, "email": email, "password": password})


def login(client, email=USER_EMAIL, password=PASSWORD):
    return client.post("/auth/login", json={"email": email, "password": password})


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def test_register_returns_tokens_that_work(anon_client):
    r = register(anon_client)
    assert r.status_code == 201
    body = r.json()
    assert body["token_type"] == "bearer" and body["expires_in"] == 15 * 60
    assert anon_client.get(PROTECTED, headers=bearer(body["access_token"])).status_code == 200


def test_register_creates_a_normal_user_with_hashed_password(anon_client, db_session):
    register(anon_client)
    user = db_session.scalar(select(User).where(User.email == "new@test.dev"))
    assert user.role == "user"
    assert user.password_hash != PASSWORD and user.password_hash.startswith("$2")


def test_register_normalizes_email_and_rejects_duplicates(anon_client):
    assert register(anon_client, email="Mixed@Test.dev").status_code == 201
    assert register(anon_client, email="mixed@test.dev").status_code == 409


@pytest.mark.parametrize(
    "payload",
    [
        {"name": "A", "email": "not-an-email", "password": PASSWORD},
        {"name": "A", "email": "a@test.dev", "password": "short"},
        {"name": "", "email": "a@test.dev", "password": PASSWORD},
    ],
)
def test_register_validates_input(anon_client, payload):
    assert anon_client.post("/auth/register", json=payload).status_code == 422


def test_login_success(anon_client):
    r = login(anon_client)
    assert r.status_code == 200
    claims = jwt.decode(r.json()["access_token"], settings.jwt_secret, algorithms=["HS256"])
    assert claims["role"] == "user" and claims["name"] == "Regular"
    assert claims["exp"] - claims["iat"] == 15 * 60


def test_wrong_email_and_wrong_password_give_identical_errors(anon_client):
    wrong_password = login(anon_client, password="wrong-password")
    wrong_email = login(anon_client, email="nobody@test.dev")
    assert wrong_password.status_code == wrong_email.status_code == 401
    assert wrong_password.json() == wrong_email.json() == {"detail": "Invalid email or password."}


def test_protected_routes_need_a_token(anon_client):
    for path in [PROTECTED, "/search?q=kafka", "/analytics/summary", "/documents/1", "/tags/top-bookmarked"]:
        r = anon_client.get(path)
        assert r.status_code == 401, path
        assert r.headers["www-authenticate"] == "Bearer"


def test_garbage_expired_wrong_secret_and_alg_none_tokens_are_rejected(anon_client, db_session):
    user = db_session.scalar(select(User).where(User.email == USER_EMAIL))
    now = datetime.now(timezone.utc)
    claims = {"sub": str(user.id), "role": "admin", "exp": now + timedelta(minutes=5)}
    expired = jwt.encode({**claims, "exp": now - timedelta(seconds=1)}, settings.jwt_secret, algorithm="HS256")
    wrong_secret = jwt.encode(claims, "another-secret-that-is-long-enough-1234", algorithm="HS256")
    alg_none = jwt.encode(claims, None, algorithm="none")
    no_exp = jwt.encode({"sub": str(user.id)}, settings.jwt_secret, algorithm="HS256")
    for token in ["garbage", expired, wrong_secret, alg_none, no_exp]:
        assert anon_client.get(PROTECTED, headers=bearer(token)).status_code == 401


def test_token_for_a_deleted_user_is_rejected(anon_client, db_session):
    token = register(anon_client).json()["access_token"]
    db_session.delete(db_session.scalar(select(User).where(User.email == "new@test.dev")))
    db_session.commit()
    assert anon_client.get(PROTECTED, headers=bearer(token)).status_code == 401


def test_refresh_tokens_are_stored_hashed(anon_client, db_session):
    raw = login(anon_client).json()["refresh_token"]
    stored = db_session.scalars(select(RefreshToken)).all()
    assert len(stored) == 1
    assert stored[0].token_hash == hash_refresh_token(raw) and stored[0].token_hash != raw


def test_refresh_rotates_tokens(anon_client, db_session):
    first = login(anon_client).json()
    r = anon_client.post("/auth/refresh", json={"refresh_token": first["refresh_token"]})
    assert r.status_code == 200
    second = r.json()
    assert second["refresh_token"] != first["refresh_token"]
    assert anon_client.get(PROTECTED, headers=bearer(second["access_token"])).status_code == 200
    rows = db_session.scalars(select(RefreshToken).order_by(RefreshToken.id)).all()
    assert rows[0].revoked_at is not None and rows[1].revoked_at is None


def test_reusing_a_rotated_refresh_token_revokes_the_whole_family(anon_client):
    first = login(anon_client).json()
    second = anon_client.post("/auth/refresh", json={"refresh_token": first["refresh_token"]}).json()
    reuse = anon_client.post("/auth/refresh", json={"refresh_token": first["refresh_token"]})
    assert reuse.status_code == 401
    assert anon_client.post("/auth/refresh", json={"refresh_token": second["refresh_token"]}).status_code == 401


def test_unknown_and_expired_refresh_tokens_are_rejected(anon_client, db_session):
    assert anon_client.post("/auth/refresh", json={"refresh_token": "nope"}).status_code == 401
    raw = login(anon_client).json()["refresh_token"]
    row = db_session.scalar(select(RefreshToken))
    row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db_session.commit()
    assert anon_client.post("/auth/refresh", json={"refresh_token": raw}).status_code == 401


def test_refresh_token_lives_seven_days(anon_client, db_session):
    login(anon_client)
    row = db_session.scalar(select(RefreshToken))
    expires = row.expires_at if row.expires_at.tzinfo else row.expires_at.replace(tzinfo=timezone.utc)
    assert timedelta(days=6, hours=23) < expires - datetime.now(timezone.utc) <= timedelta(days=7)


def test_logout_revokes_the_refresh_token(anon_client):
    raw = login(anon_client).json()["refresh_token"]
    assert anon_client.post("/auth/logout", json={"refresh_token": raw}).status_code == 204
    assert anon_client.post("/auth/refresh", json={"refresh_token": raw}).status_code == 401
    assert anon_client.post("/auth/logout", json={"refresh_token": raw}).status_code == 204
    assert anon_client.post("/auth/logout", json={"refresh_token": "unknown"}).status_code == 204


def test_search_events_record_the_user(client, db_session):
    client.get("/search", params={"q": "kafka"})
    event = db_session.scalar(select(SearchEvent))
    user = db_session.scalar(select(User).where(User.email == USER_EMAIL))
    assert event.user_id == user.id


@pytest.fixture()
def docs_api(db_session, make_client):
    engine = SearchEngine()
    build = lambda email: make_client(engine, email=email)
    return engine, build


def test_only_admins_can_create_edit_and_delete_documents(db_session, docs_api):
    engine, build = docs_api
    payload = {"title": "Zookeeper Basics", "body": "Coordination service notes.", "tags": ["Kafka", "backend"]}

    assert build(None).post("/documents", json=payload).status_code == 401
    user = build(USER_EMAIL)
    assert user.post("/documents", json=payload).status_code == 403
    assert user.put("/documents/1", json=payload).status_code == 403
    assert user.delete("/documents/1").status_code == 403

    admin = build(ADMIN_EMAIL)
    created = admin.post("/documents", json=payload)
    assert created.status_code == 201
    doc = created.json()
    assert doc["status"] == "indexed" and doc["tags"] == ["backend", "kafka"]
    assert [h.title for h in engine.search("zookeeper").hits] == ["Zookeeper Basics"]

    updated = admin.put(f"/documents/{doc['id']}", json={"title": "Raft Consensus", "body": "Leader election.", "tags": ["backend"]})
    assert updated.status_code == 200
    assert engine.search("zookeeper").total == 0
    assert engine.search("raft").total == 1

    assert admin.delete(f"/documents/{doc['id']}").status_code == 204
    assert engine.search("raft").total == 0
    assert db_session.get(Document, doc["id"]) is None
    assert admin.delete(f"/documents/{doc['id']}").status_code == 404


def test_admin_document_validation(docs_api):
    _, build = docs_api
    admin = build(ADMIN_EMAIL)
    assert admin.post("/documents", json={"title": "", "body": "x"}).status_code == 422
    assert admin.put("/documents/999", json={"title": "t", "body": "b"}).status_code == 404
