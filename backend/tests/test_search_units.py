from datetime import datetime, timezone

from app.search.engine import SearchEngine
from app.search.fuzzy import allowed_distance, closest_terms, levenshtein
from app.search.index import InvertedIndex
from app.search.snippets import make_snippet
from app.search.tokenizer import tokenize
from app.search.trie import Trie


def utc(y, m, d):
    return datetime(y, m, d, tzinfo=timezone.utc)


def test_tokenizer_lowercases_strips_punctuation_and_stop_words():
    assert tokenize("The Quick, Brown Fox!") == ["quick", "brown", "fox"]
    assert tokenize("Redis Pub/Sub: it's fast") == ["redis", "pub", "sub", "fast"]
    assert tokenize("HTTP/2 and TLS") == ["http", "2", "tls"]
    assert tokenize("") == [] and tokenize("the of and") == []


def test_trie_prefix_and_ranking():
    trie = Trie()
    for w in ["kafka", "kafak", "kernel", "redis"]:
        trie.insert(w)
    weights = {"kafka": 10, "kafak": 1, "kernel": 5, "redis": 3}
    assert sorted(trie.words_with_prefix("ka")) == ["kafak", "kafka"]
    assert trie.suggest("k", k=2, weight=weights.get) == ["kafka", "kernel"]
    assert trie.suggest("zzz") == []
    assert trie.contains("redis") and not trie.contains("red")


def test_trie_suggest_skips_zero_weight_words():
    trie = Trie()
    trie.insert("gone")
    trie.insert("good")
    assert trie.suggest("go", weight=lambda w: 0 if w == "gone" else 1) == ["good"]


def test_levenshtein_distances():
    assert levenshtein("kafka", "kafka") == 0
    assert levenshtein("kafak", "kafka") == 2
    assert levenshtein("kitten", "sitting") == 3
    assert levenshtein("", "abc") == 3


def test_levenshtein_early_exit_reports_over_limit():
    assert levenshtein("elephant", "cat", max_dist=2) > 2
    assert levenshtein("redis", "redsi", max_dist=2) == 2


def test_short_words_get_no_fuzziness():
    assert allowed_distance("cat") == 0 and allowed_distance("kafk") == 1 and allowed_distance("kafak") == 2
    assert closest_terms("cat", ["car", "cap"], lambda w: 1) == []


def test_closest_terms_prefers_smaller_distance_then_frequency():
    freq = {"redis": 5, "reads": 50, "redux": 9}.get
    found = closest_terms("redit", ["redis", "reads", "redux"], freq)
    assert found[0] == ("redis", 1)


def test_index_stores_term_frequencies_with_title_boost():
    idx = InvertedIndex()
    idx.add(1, "Kafka", "kafka kafka streams", [], 1, utc(2025, 1, 1))
    assert idx.postings["kafka"][1] == 5
    assert idx.postings["streams"][1] == 1


def test_indexing_the_same_document_twice_is_idempotent():
    idx = InvertedIndex()
    for _ in range(3):
        idx.add(1, "Redis caching", "cache aside pattern", ["caching"], 1, utc(2025, 1, 1))
    snapshot = ({t: dict(p) for t, p in idx.postings.items()}, idx.n_docs, idx.avg_doc_length)

    idx.add(1, "Redis caching", "cache aside pattern", ["caching"], 1, utc(2025, 1, 1))
    assert ({t: dict(p) for t, p in idx.postings.items()}, idx.n_docs, idx.avg_doc_length) == snapshot
    assert idx.n_docs == 1


def test_updating_a_document_removes_its_old_terms():
    idx = InvertedIndex()
    idx.add(1, "Old title", "obsolete words", [], 1, utc(2025, 1, 1))
    idx.add(1, "New title", "fresh words", [], 1, utc(2025, 1, 1))
    assert "obsolete" not in idx.postings and "fresh" in idx.postings


def test_remove_document_and_stale_suggestions():
    eng = SearchEngine()
    eng.add_document(1, "Kubernetes", "pods", [], 1, utc(2025, 1, 1))
    assert eng.suggest("kub") == ["kubernetes"]
    assert eng.remove_document(1) is True and eng.remove_document(1) is False
    assert eng.suggest("kub") == []
    assert eng.search("kubernetes").total == 0


def test_title_match_beats_body_match():
    eng = SearchEngine()
    eng.add_document(1, "Cooking notes", "kafka is mentioned here once among many other filler words today", [], 1, utc(2025, 1, 1))
    eng.add_document(2, "Kafka", "some other filler words that fill this body up nicely for length parity", [], 1, utc(2025, 1, 1))
    assert [h.id for h in eng.search("kafka").hits] == [2, 1]


def test_docs_matching_all_terms_beat_docs_matching_one():
    eng = SearchEngine()
    eng.add_document(1, "Notes", "cache cache cache cache", [], 1, utc(2025, 1, 1))
    eng.add_document(2, "Redis cache", "short", [], 1, utc(2025, 1, 1))
    assert eng.search("redis cache").hits[0].id == 2


def make_filter_engine():
    eng = SearchEngine()
    eng.add_document(1, "Redis a", "redis", ["caching", "backend"], author_id=1, created_at=utc(2025, 1, 10))
    eng.add_document(2, "Redis b", "redis", ["caching"], author_id=2, created_at=utc(2025, 3, 10))
    eng.add_document(3, "Redis c", "redis", ["backend"], author_id=1, created_at=utc(2025, 6, 10))
    return eng


def ids(result):
    return sorted(h.id for h in result.hits)


def test_filters_combine_with_the_query():
    from datetime import date
    eng = make_filter_engine()
    assert ids(eng.search("redis", tags=["caching"])) == [1, 2]
    assert ids(eng.search("redis", tags=["caching", "backend"])) == [1]
    assert ids(eng.search("redis", author_id=1)) == [1, 3]
    assert ids(eng.search("redis", date_from=date(2025, 2, 1), date_to=date(2025, 6, 10))) == [2, 3]
    assert ids(eng.search("redis", tags=["backend"], author_id=1, date_from=date(2025, 2, 1))) == [3]


def test_sort_newest_and_pagination():
    eng = make_filter_engine()
    assert [h.id for h in eng.search("redis", sort="newest").hits] == [3, 2, 1]
    assert [h.id for h in eng.search("redis", sort="oldest").hits] == [1, 2, 3]
    page1 = eng.search("redis", sort="oldest", page=1, limit=2)
    page2 = eng.search("redis", sort="oldest", page=2, limit=2)
    assert page1.total == page2.total == 3
    assert [h.id for h in page1.hits] == [1, 2] and [h.id for h in page2.hits] == [3]


def test_facets_count_tags_of_matching_docs():
    assert make_filter_engine().search("redis").facets == {"caching": 2, "backend": 2}


def test_snippet_is_html_escaped():
    out = make_snippet("<script>alert(1)</script> kafka rocks", {"kafka"})
    assert "<script>" not in out and "&lt;script&gt;" in out and "<mark>kafka</mark>" in out


def test_snippet_centres_on_match_and_adds_ellipses():
    body = ("filler " * 60) + "the kafka consumer group appears here " + ("filler " * 60)
    out = make_snippet(body, {"kafka", "consumer", "group"}, width=100)
    assert out.startswith("…") and out.endswith("…")
    assert "<mark>kafka</mark> <mark>consumer</mark> <mark>group</mark>" in out
    assert len(out) < 200


def test_snippet_falls_back_to_start_of_body_when_only_title_matched():
    assert make_snippet("plain body text", {"missing"}).startswith("plain body")
