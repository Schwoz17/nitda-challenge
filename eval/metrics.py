import math
from collections import Counter

from normaliser import normalise
from normaliser.numbers import fold


def _tokens(text):
    return [t for t in (fold(w) for w in text.split()) if t]


def edit_distance(a, b):
    prev = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        cur = [i]
        for j, y in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (x != y)))
        prev = cur
    return prev[-1]


def wer(pairs):
    errors = total = 0
    for ref, hyp in pairs:
        r = _tokens(ref)
        errors += edit_distance(r, _tokens(hyp))
        total += len(r)
    return errors / total if total else 0.0


def number_error_rate(pairs, lang):
    missed = total = 0
    for ref, hyp in pairs:
        want = Counter(a.value for a in normalise(ref, lang).amounts)
        got = Counter(a.value for a in normalise(hyp, lang).amounts)
        missed += sum((want - got).values())
        total += sum(want.values())
    return missed / total if total else 0.0


def term_recall(pairs, terms):
    terms = [fold(t) for t in terms]
    seen = found = 0
    for ref, hyp in pairs:
        r, h = " ".join(_tokens(ref)), " ".join(_tokens(hyp))
        for t in terms:
            if t in r:
                seen += 1
                found += t in h
    return found / seen if seen else None


def spec_matches(pred, ref):
    key = lambda s: (s.get("template"), sorted((f["name"], f["type"]) for f in s.get("fields", [])))
    return key(pred) == key(ref)


def rate(hits, n):
    if n == 0:
        return {"n": 0, "rate": None, "ci95": None}
    p = hits / n
    z = 1.96
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return {"n": n, "rate": round(p, 4), "ci95": [round(max(0, centre - half), 4), round(min(1, centre + half), 4)]}
