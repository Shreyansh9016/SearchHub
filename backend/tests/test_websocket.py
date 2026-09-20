from contextlib import nullcontext
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from sqlalchemy import select
from starlette.websockets import WebSocketDisconnect

from app import realtime
from app.config import settings
from app.models import Document, Tag, User
from app.search.loader import build_engine
from app.security import create_access_token
from tests.conftest import ADMIN_EMAIL, USER_EMAIL, auth_headers

TITLE = "Redis Streams Explained"


def token_for(db, email):
    return create_access_token(db.scalar(select(User).where(User.email == email)))


@pytest.fixture()
def live(db_session, make_client, monkeypatch):
    monkeypatch.setattr("app.main.SessionLocal", lambda: nullcontext(db_session))
    admin = db_session.scalar(select(User).where(User.email == ADMIN_EMAIL))
    db_session.add(
        Document(title=TITLE, body="Streams are append-only logs.", author_id=admin.id, status="indexed", tags=[Tag(name="redis")])
    )
    db_session.commit()
    client = make_client(build_engine(db_session))
    with client:
        yield client


def connect(client, db, email=USER_EMAIL):
    return client.websocket_connect(f"/ws?token={token_for(db, email)}")


def open_socket(stack, client, db, email=USER_EMAIL):
    ws = stack.enter_context(connect(client, db, email))
    assert ws.receive_json() == {"type": "connected"}
    return ws


@pytest.fixture()
def stack():
    from contextlib import ExitStack

    with ExitStack() as s:
        yield s


@pytest.mark.parametrize("query", ["", "?token=garbage"])
def test_missing_or_bad_token_is_rejected(live, query):
    with live.websocket_connect(f"/ws{query}") as ws:
        with pytest.raises(WebSocketDisconnect) as exc:
            ws.receive_json()
    assert exc.value.code == 4401


def test_expired_token_is_rejected(live, db_session):
    user = db_session.scalar(select(User).where(User.email == USER_EMAIL))
    now = datetime.now(timezone.utc)
    expired = jwt.encode({"sub": str(user.id), "exp": now - timedelta(seconds=5)}, settings.jwt_secret, algorithm="HS256")
    with live.websocket_connect(f"/ws?token={expired}") as ws:
        with pytest.raises(WebSocketDisconnect) as exc:
            ws.receive_json()
    assert exc.value.code == 4401


def test_valid_token_connects_and_is_tracked(live, db_session):
    with connect(live, db_session) as ws:
        assert ws.receive_json() == {"type": "connected"}
        assert len(realtime.manager.connections) == 1
    assert realtime.manager.connections == {}


def test_server_sends_heartbeat_pings(live, db_session, monkeypatch):
    monkeypatch.setattr(realtime, "PING_SECONDS", 0.05)
    with connect(live, db_session) as ws:
        assert ws.receive_json() == {"type": "connected"}
        assert ws.receive_json() == {"type": "ping"}
        ws.send_json({"type": "pong"})
        assert ws.receive_json() == {"type": "ping"}


def test_silent_connection_is_closed_after_idle_timeout(live, db_session, monkeypatch):
    monkeypatch.setattr(realtime, "IDLE_TIMEOUT", 0.2)
    monkeypatch.setattr(realtime, "PING_SECONDS", 30)
    with connect(live, db_session) as ws:
        assert ws.receive_json() == {"type": "connected"}
        with pytest.raises(WebSocketDisconnect) as exc:
            ws.receive_json()
    assert exc.value.code == 1001


def test_connection_is_closed_when_the_access_token_expires(live, db_session):
    user = db_session.scalar(select(User).where(User.email == USER_EMAIL))
    short = jwt.encode(
        {"sub": str(user.id), "exp": datetime.now(timezone.utc) + timedelta(seconds=2)},
        settings.jwt_secret,
        algorithm="HS256",
    )
    with live.websocket_connect(f"/ws?token={short}") as ws:
        assert ws.receive_json() == {"type": "connected"}
        with pytest.raises(WebSocketDisconnect) as exc:
            ws.receive_json()
    assert exc.value.code == 4401


def test_search_pushes_trending_to_connected_users(live, db_session, stack):
    ws = open_socket(stack, live, db_session)
    live.get("/search", params={"q": "redis"})
    assert ws.receive_json() == {"type": "trending", "queries": [{"query": "redis", "count": 1}]}


def test_bookmark_pushes_activity_feed_to_everyone(live, db_session, stack):
    user_ws = open_socket(stack, live, db_session, USER_EMAIL)
    admin_ws = open_socket(stack, live, db_session, ADMIN_EMAIL)
    assert live.put("/documents/1/bookmark").status_code == 200
    for ws in (user_ws, admin_ws):
        message = ws.receive_json()
        assert message["type"] == "activity"
        assert message["message"] == f"Someone bookmarked {TITLE}"
        assert message["document_id"] == 1

    live.put("/documents/1/bookmark")
    live.get("/search", params={"q": "redis"})
    assert user_ws.receive_json()["type"] == "trending"


def test_updating_a_document_notifies_only_users_who_bookmarked_it(live, db_session, stack):
    user_ws = open_socket(stack, live, db_session, USER_EMAIL)
    admin_ws = open_socket(stack, live, db_session, ADMIN_EMAIL)
    live.put("/documents/1/bookmark")
    assert user_ws.receive_json()["type"] == "activity"
    assert admin_ws.receive_json()["type"] == "activity"

    admin_headers = auth_headers(db_session, ADMIN_EMAIL)
    response = live.put(
        "/documents/1", json={"title": TITLE, "body": "Rewritten body.", "tags": ["redis"]}, headers=admin_headers
    )
    assert response.status_code == 200
    assert user_ws.receive_json() == {
        "type": "notification",
        "message": f'"{TITLE}" was updated',
        "document_id": 1,
    }

    live.get("/search", params={"q": "redis"})
    assert user_ws.receive_json()["type"] == "trending"
    assert admin_ws.receive_json()["type"] == "trending"


def test_no_broadcast_work_without_listeners(live, db_session):
    assert realtime.manager.connections == {}
    assert live.get("/search", params={"q": "redis"}).status_code == 200
    assert live.put("/documents/1/bookmark").status_code == 200
