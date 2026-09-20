import math
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, time as dtime, timedelta, timezone

from app.search.fuzzy import closest_terms
from app.search.index import DocRecord, InvertedIndex
from app.search.snippets import make_snippet
from app.search.tokenizer import tokenize

K1 = 1.5
B = 0.75


class EmptyQueryError(ValueError):
    pass


@dataclass
class Hit:
    id: int
    title: str
    snippet: str
    score: float
    tags: list[str]
    author_id: int
    created_at: datetime


@dataclass
class SearchResult:
    query: str
    total: int
    page: int
    limit: int
    took_ms: float
    hits: list[Hit]
    facets: dict[str, int] = field(default_factory=dict)


@dataclass
class _QueryTerm:
    original: str
    matches: list[tuple[str, float]]


class SearchEngine:
    def __init__(self):
        self.index = InvertedIndex()

    def add_document(self, doc_id, title, body, tags=(), author_id=0, created_at=None):
        self.index.add(doc_id, title, body, tags, author_id, created_at or datetime.now(timezone.utc))

    def remove_document(self, doc_id) -> bool:
        return self.index.remove(doc_id)

    def _idf(self, term: str) -> float:
        n, df = self.index.n_docs, self.index.doc_freq(term)
        return math.log(1 + (n - df + 0.5) / (df + 0.5))

    def _bm25(self, term: str, doc: DocRecord, tf: float, idf: float) -> float:
        avgdl = self.index.avg_doc_length or 1.0
        norm = tf + K1 * (1 - B + B * doc.length / avgdl)
        return idf * tf * (K1 + 1) / norm

    def _resolve_terms(self, tokens: list[str]) -> list[_QueryTerm]:
        resolved = []
        for tok in tokens:
            if self.index.doc_freq(tok):
                resolved.append(_QueryTerm(tok, [(tok, 1.0)]))
                continue
            close = closest_terms(tok, self.index.vocabulary, self.index.doc_freq)
            resolved.append(_QueryTerm(tok, [(w, 1 / (1 + d)) for w, d in close]))
        return resolved

    def search(
        self,
        q: str,
        tags: list[str] | None = None,
        author_id: int | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        sort: str = "relevance",
        page: int = 1,
        limit: int = 10,
    ) -> SearchResult:
        started = time.perf_counter()
        tokens = list(dict.fromkeys(tokenize(q)))
        if not tokens:
            raise EmptyQueryError("Query must contain at least one searchable word.")

        query_terms = [qt for qt in self._resolve_terms(tokens) if qt.matches]

        candidates: set[int] = set()
        for qt in query_terms:
            for term, _ in qt.matches:
                candidates.update(self.index.postings[term])
        candidates = {d for d in candidates if self._passes_filters(self.index.docs[d], tags, author_id, date_from, date_to)}

        idfs = {term: self._idf(term) for qt in query_terms for term, _ in qt.matches}
        scored: list[tuple[float, DocRecord]] = []
        facet_counter: Counter = Counter()
        for doc_id in candidates:
            doc = self.index.docs[doc_id]
            total, matched = 0.0, 0
            for qt in query_terms:
                best = 0.0
                for term, weight in qt.matches:
                    tf = self.index.postings[term].get(doc_id)
                    if tf:
                        best = max(best, weight * self._bm25(term, doc, tf, idfs[term]))
                if best > 0:
                    total += best
                    matched += 1
            scored.append((total * matched / len(query_terms), doc))
            facet_counter.update(doc.tags)

        if sort == "newest":
            scored.sort(key=lambda s: (-s[1].created_at.timestamp(), s[1].id))
        elif sort == "oldest":
            scored.sort(key=lambda s: (s[1].created_at.timestamp(), s[1].id))
        else:
            scored.sort(key=lambda s: (-s[0], s[1].id))

        highlight_terms = {term for qt in query_terms for term, _ in qt.matches}
        offset = (page - 1) * limit
        hits = [
            Hit(
                id=doc.id,
                title=doc.title,
                snippet=make_snippet(doc.body, highlight_terms),
                score=round(score, 4),
                tags=sorted(doc.tags),
                author_id=doc.author_id,
                created_at=doc.created_at,
            )
            for score, doc in scored[offset: offset + limit]
        ]
        return SearchResult(
            query=q,
            total=len(scored),
            page=page,
            limit=limit,
            took_ms=round((time.perf_counter() - started) * 1000, 2),
            hits=hits,
            facets=dict(facet_counter.most_common()),
        )

    @staticmethod
    def _passes_filters(doc: DocRecord, tags, author_id, date_from, date_to) -> bool:
        if tags and not {t.lower() for t in tags} <= doc.tags:
            return False
        if author_id is not None and doc.author_id != author_id:
            return False
        if date_from and doc.created_at < datetime.combine(date_from, dtime.min, timezone.utc):
            return False
        if date_to and doc.created_at >= datetime.combine(date_to + timedelta(days=1), dtime.min, timezone.utc):
            return False
        return True

    def related(self, doc_id: int, limit: int = 5) -> list[Hit]:
        record = self.index.docs.get(doc_id)
        if record is None:
            return []
        try:
            result = self.search(record.title, limit=limit + 1)
        except EmptyQueryError:
            return []
        return [h for h in result.hits if h.id != doc_id][:limit]

    def suggest(self, prefix: str, k: int = 5) -> list[str]:
        words = prefix.lower().split()
        if not words:
            return []
        head, last = words[:-1], words[-1]
        completions = self.index.trie.suggest(last, k, weight=self.index.doc_freq)
        return [" ".join(head + [c]) for c in completions]
