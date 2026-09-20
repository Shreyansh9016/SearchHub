import heapq
from typing import Callable, Iterator


class _Node:
    __slots__ = ("children", "is_word")

    def __init__(self):
        self.children: dict[str, "_Node"] = {}
        self.is_word = False


class Trie:
    def __init__(self):
        self.root = _Node()

    def insert(self, word: str) -> None:
        node = self.root
        for ch in word:
            node = node.children.setdefault(ch, _Node())
        node.is_word = True

    def _find(self, prefix: str) -> _Node | None:
        node = self.root
        for ch in prefix:
            node = node.children.get(ch)
            if node is None:
                return None
        return node

    def contains(self, word: str) -> bool:
        node = self._find(word)
        return bool(node and node.is_word)

    def words_with_prefix(self, prefix: str) -> Iterator[str]:
        start = self._find(prefix)
        if start is None:
            return
        stack = [(start, prefix)]
        while stack:
            node, word = stack.pop()
            if node.is_word:
                yield word
            for ch, child in node.children.items():
                stack.append((child, word + ch))

    def suggest(self, prefix: str, k: int = 5, weight: Callable[[str], float] = lambda w: 1) -> list[str]:
        scored = ((weight(w), w) for w in self.words_with_prefix(prefix))
        top = heapq.nsmallest(k, ((-s, w) for s, w in scored if s > 0))
        return [w for _, w in top]
