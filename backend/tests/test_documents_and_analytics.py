import pytest
from sqlalchemy import select

from app.models import Document, Tag, User
from app.search.loader import build_engine
from tests.conftest import ADMIN_EMAIL


@pytest.fixture()
def api(db_session, make_client):
    author = db_session.scalar(select(User).where(User.email == ADMIN_EMAIL))
    kafka, caching = Tag(name="kafka"), Tag(name="caching")
    db_session.add_all(
        [
            Document(title="Kafka Consumer Groups", body="Consumer groups share partitions.", author_id=author.id, status="indexed", tags=[kafka]),
            Document(title="Kafka Partitions Guide", body="Partitions spread load across brokers.", author_id=author.id, status="indexed", tags=[kafka]),
            Document(title="Redis Caching Patterns", body="Cache aside with a TTL.", author_id=author.id, status="indexed", tags=[caching]),
        ]
    )
    db_session.commit()
    return make_client(build_engine(db_session))


def test_get_document_includes_related_and_bookmark_state(api):
    r = api.get("/documents/1")
    assert r.status_code == 200
    body = r.json()
    assert body["title"] == "Kafka Consumer Groups"
    assert body["tags"] == ["kafka"]
    assert body["bookmarked"] is False
    assert [x["id"] for x in body["related"]] == [2]


def test_missing_document_is_404(api):
    assert api.get("/documents/999").status_code == 404
    assert api.put("/documents/999/bookmark").status_code == 404


def test_bookmark_toggle_is_idempotent(api):
    assert api.put("/documents/1/bookmark").json() == {"document_id": 1, "bookmarked": True}
    assert api.put("/documents/1/bookmark").json()["bookmarked"] is True
    assert api.get("/documents/1").json()["bookmarked"] is True
    assert api.delete("/documents/1/bookmark").json()["bookmarked"] is False
    assert api.delete("/documents/1/bookmark").json()["bookmarked"] is False
    assert api.get("/documents/1").json()["bookmarked"] is False


def test_top_bookmarked_tags(api):
    api.put("/documents/1/bookmark")
    api.put("/documents/2/bookmark")
    api.put("/documents/3/bookmark")
    assert api.get("/tags/top-bookmarked").json() == [
        {"name": "kafka", "bookmarks": 2},
        {"name": "caching", "bookmarks": 1},
    ]


def test_analytics_summary(client, db_session):
    for query, count in [("kafka", 3), ("Kafka", 1), ("xyzabc", 2)]:
        for _ in range(count):
            client.get("/search", params={"q": query})
    body = client.get("/analytics/summary").json()
    assert body["total_searches"] == 6
    assert body["zero_result_searches"] == 2
    assert body["zero_result_rate"] == pytest.approx(2 / 6, abs=1e-3)
    assert body["top_queries"][0] == {"query": "kafka", "count": 4}
    assert sum(m["count"] for m in body["per_minute"]) == 6
    assert len(body["per_minute"]) == 30


def test_analytics_empty(client):
    body = client.get("/analytics/summary").json()
    assert body["total_searches"] == 0 and body["zero_result_rate"] == 0.0
