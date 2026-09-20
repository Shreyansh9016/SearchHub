from typing import Callable, Iterable

MAX_DISTANCE = 2


def levenshtein(a: str, b: str, max_dist: int | None = None) -> int:
    if a == b:
        return 0
    if len(a) < len(b):
        a, b = b, a
    if max_dist is not None and len(a) - len(b) > max_dist:
        return max_dist + 1

    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        if max_dist is not None and min(cur) > max_dist:
            return max_dist + 1
        prev = cur
    return prev[-1]


def allowed_distance(term: str) -> int:
    if len(term) <= 3:
        return 0
    if len(term) == 4:
        return 1
    return MAX_DISTANCE


def closest_terms(
    term: str,
    vocabulary: Iterable[str],
    frequency: Callable[[str], int],
    limit: int = 3,
) -> list[tuple[str, int]]:
    max_dist = allowed_distance(term)
    if max_dist == 0:
        return []
    found = []
    for word in vocabulary:
        d = levenshtein(term, word, max_dist)
        if d <= max_dist:
            found.append((word, d))
    found.sort(key=lambda wd: (wd[1], -frequency(wd[0]), wd[0]))
    return found[:limit]
