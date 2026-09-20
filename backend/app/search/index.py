import threading
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone

from app.search.tokenizer import tokenize
from app.search.trie import Trie

TITLE_BOOST = 3


def as_utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


@dataclass(frozen=True)
class DocRecord:
    id: int
    title: str
    body: str
    tags: frozenset[str]
    author_id: int
    created_at: datetime
    length: float


class InvertedIndex:
    def __init__(self):
        self.postings: dict[str, dict[int, float]] = {}
        self.docs: dict[int, DocRecord] = {}
        self._doc_terms: dict[int, list[str]] = {}
        self._total_length = 0.0
        self.trie = Trie()
        self._lock = threading.RLock()

    @property
    def n_docs(self) -> int:
        return len(self.docs)

    @property
    def avg_doc_length(self) -> float:
        return self._total_length / len(self.docs) if self.docs else 0.0

    def doc_freq(self, term: str) -> int:
        return len(self.postings.get(term, ()))

    @property
    def vocabulary(self):
        return self.postings.keys()

    def add(self, doc_id, title, body, tags, author_id, created_at) -> None:
        with self._lock:
            self.remove(doc_id)
            title_tf = Counter(tokenize(title))
            body_tf = Counter(tokenize(body))
            weighted: Counter = Counter()
            for term, n in body_tf.items():
                weighted[term] += n
            for term, n in title_tf.items():
                weighted[term] += n * TITLE_BOOST

            length = float(sum(body_tf.values()) + TITLE_BOOST * sum(title_tf.values()))
            self.docs[doc_id] = DocRecord(
                id=doc_id, title=title, body=body,
                tags=frozenset(t.lower() for t in tags),
                author_id=author_id, created_at=as_utc(created_at), length=length,
            )
            self._doc_terms[doc_id] = list(weighted)
            self._total_length += length
            for term, tf in weighted.items():
                if term not in self.postings:
                    self.trie.insert(term)
                self.postings.setdefault(term, {})[doc_id] = tf

    def remove(self, doc_id) -> bool:
        with self._lock:
            record = self.docs.pop(doc_id, None)
            if record is None:
                return False
            self._total_length -= record.length
            for term in self._doc_terms.pop(doc_id):
                plist = self.postings[term]
                del plist[doc_id]
                if not plist:
                    del self.postings[term]
            return True
