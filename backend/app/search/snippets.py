import html

from app.search.tokenizer import WORD_RE


def _matches(text: str, terms: set[str]) -> list[tuple[int, int, str]]:
    out = []
    for m in WORD_RE.finditer(text):
        word = m.group().lower()
        if word in terms:
            out.append((m.start(), m.end(), word))
    return out


def _render(text: str, matches: list[tuple[int, int, str]], lo: int, hi: int) -> str:
    parts, pos = [], lo
    for start, end, _ in matches:
        if start < lo or end > hi:
            continue
        parts.append(html.escape(text[pos:start]))
        parts.append("<mark>" + html.escape(text[start:end]) + "</mark>")
        pos = end
    parts.append(html.escape(text[pos:hi]))
    return "".join(parts)


def make_snippet(body: str, terms: set[str], width: int = 200) -> str:
    body = " ".join(body.split())
    matches = _matches(body, terms)

    if not matches:
        lo, hi = 0, min(len(body), width)
    else:
        best_i, best_score = 0, -1
        for i, (start, _, _) in enumerate(matches):
            score = len({t for s, _, t in matches[i:] if s < start + width})
            if score > best_score:
                best_i, best_score = i, score
        lo = max(0, matches[best_i][0] - width // 5)
        hi = min(len(body), lo + width)
        first = matches[best_i][0]
        if lo > 0:
            snapped = body.find(" ", lo) + 1
            if 0 < snapped <= first:
                lo = snapped
        if hi < len(body):
            snapped = body.rfind(" ", lo, hi)
            if snapped > lo:
                hi = snapped

    text = _render(body, matches, lo, hi)
    return ("…" if lo > 0 else "") + text + ("…" if hi < len(body) else "")
