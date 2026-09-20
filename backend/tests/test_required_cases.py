import pytest

from app.search.engine import EmptyQueryError

ABOUT = {"Kafka Consumer Groups Explained", "Tuning Kafka Consumer Group Rebalances"}
ONLY_MENTION = {"Redis Streams Explained", "Choosing a Message Broker"}


def titles(result):
    return [h.title for h in result.hits]


def test_kafka_consumer_group_ranks_focused_articles_first(engine):
    result = engine.search("kafka consumer group", limit=50)
    ranked = titles(result)

    assert set(ranked[:2]) == ABOUT, ranked[:5]
    for mention in ONLY_MENTION:
        assert mention in ranked, "mention-only article should still match"
        assert ranked.index(mention) > max(ranked.index(t) for t in ABOUT)


def test_title_matches_outrank_body_only_matches(engine):
    result = engine.search("kafka consumer group", limit=50)
    by_title = {h.title: h.score for h in result.hits}
    assert by_title["Kafka Consumer Groups Explained"] > by_title["Choosing a Message Broker"]


def test_typo_still_returns_kafka_articles(engine):
    result = engine.search("kafak", limit=20)
    assert result.total > 0
    assert all("kafka" in h.tags or "kafka" in h.snippet.lower() for h in result.hits[:10])
    assert "Kafka Consumer Groups Explained" in titles(result) or result.total > 20


def test_multiple_typos_in_one_query(engine):
    result = engine.search("redsi cachng")
    assert result.total > 0


def test_redis_with_tag_caching(engine):
    result = engine.search("redis", tags=["caching"], limit=50)
    assert result.total > 0
    assert all("caching" in h.tags for h in result.hits)
    scores = [h.score for h in result.hits]
    assert scores == sorted(scores, reverse=True)
    assert "redis" in result.hits[0].title.lower()


def test_nonsense_query_returns_empty_without_error(engine):
    result = engine.search("xyzabc")
    assert result.total == 0
    assert result.hits == []


@pytest.mark.parametrize("q", ["", "   ", "!!!", "the of and"])
def test_query_without_searchable_terms_raises(engine, q):
    with pytest.raises(EmptyQueryError):
        engine.search(q)


def test_suggest_kaf_returns_kafka(engine):
    suggestions = engine.suggest("kaf")
    assert suggestions[0] == "kafka"
    assert len(suggestions) <= 5


def test_api_kafka_consumer_group(client):
    r = client.get("/search", params={"q": "kafka consumer group"})
    assert r.status_code == 200
    body = r.json()
    assert {h["title"] for h in body["results"][:2]} == ABOUT
    assert "<mark>" in body["results"][0]["snippet"]


def test_api_typo(client):
    r = client.get("/search", params={"q": "kafak"})
    assert r.status_code == 200
    assert r.json()["total"] > 0


def test_api_tag_filter(client):
    r = client.get("/search?q=redis+cache&tag=caching")
    assert r.status_code == 200
    results = r.json()["results"]
    assert results and all("caching" in h["tags"] for h in results)


def test_api_nonsense_is_empty_200(client):
    r = client.get("/search", params={"q": "xyzabc"})
    assert r.status_code == 200
    assert r.json()["total"] == 0 and r.json()["results"] == []


@pytest.mark.parametrize("params", [{"q": ""}, {}, {"q": "   "}, {"q": "the and of"}])
def test_api_empty_query_is_400_with_message(client, params):
    r = client.get("/search", params=params)
    assert r.status_code == 400
    assert r.json()["detail"]


def test_api_suggest(client):
    r = client.get("/search/suggest", params={"prefix": "kaf"})
    assert r.status_code == 200
    assert "kafka" in r.json()["suggestions"]
    assert client.get("/search/suggest", params={"prefix": ""}).status_code == 400
