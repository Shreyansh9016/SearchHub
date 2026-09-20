from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app
from app.models import User
from app.routers.search import get_engine
from app.search.engine import SearchEngine
from app.security import create_access_token, hash_password
from scripts.seed_data import generate_articles

FIXED_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
PASSWORD = "password123"
USER_EMAIL = "user@test.dev"
ADMIN_EMAIL = "admin@test.dev"


@pytest.fixture(scope="session")
def articles():
    return generate_articles(520, seed=42, now=FIXED_NOW)


@pytest.fixture(scope="session")
def engine(articles):
    eng = SearchEngine()
    for i, a in enumerate(articles, start=1):
        eng.add_document(i, a["title"], a["body"], a["tags"], author_id=1, created_at=a["created_at"])
    return eng


@pytest.fixture()
def db_session():
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    session = sessionmaker(bind=eng, autoflush=False, expire_on_commit=False)()
    session.add_all(
        [
            User(name="Regular", email=USER_EMAIL, password_hash=hash_password(PASSWORD), role="user"),
            User(name="Admin", email=ADMIN_EMAIL, password_hash=hash_password(PASSWORD), role="admin"),
        ]
    )
    session.commit()
    yield session
    session.close()


def auth_headers(db_session, email):
    user = db_session.scalar(select(User).where(User.email == email))
    return {"Authorization": f"Bearer {create_access_token(user)}"}


@pytest.fixture()
def make_client(db_session):
    def build(search_engine, email=USER_EMAIL):
        app.dependency_overrides[get_engine] = lambda: search_engine
        app.dependency_overrides[get_db] = lambda: db_session
        headers = auth_headers(db_session, email) if email else {}
        return TestClient(app, headers=headers)

    yield build
    app.dependency_overrides.clear()


@pytest.fixture()
def client(engine, make_client):
    return make_client(engine)


@pytest.fixture()
def anon_client(engine, make_client):
    return make_client(engine, email=None)
