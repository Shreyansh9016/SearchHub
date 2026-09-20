import re

STOP_WORDS = frozenset(
    """
    a about after all also am an and any are as at be because been before being but by can could did do
    does doing for from had has have having he her here hers him his how i if in into is it its just me
    more most my no nor not of on once only or other our out over own same she should so some such than
    that the their them then there these they this those through to too under until up us very was we
    were what when where which while who whom why will with would you your
    """.split()
)

WORD_RE = re.compile(r"[^\W_]+", re.UNICODE)


def tokenize(text: str) -> list[str]:
    text = text.lower().replace("'", "").replace("’", "")
    return [
        tok
        for tok in WORD_RE.findall(text)
        if tok not in STOP_WORDS and (len(tok) > 1 or tok.isdigit())
    ]
