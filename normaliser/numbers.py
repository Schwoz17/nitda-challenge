import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

_STRIP = str.maketrans({"ɗ": "d", "ƙ": "k", "ɓ": "b", "'": "", "’": "", "ʼ": "", "-": ""})


def fold(word):
    word = unicodedata.normalize("NFD", word.lower())
    word = "".join(c for c in word if not unicodedata.combining(c))
    return word.translate(_STRIP).strip(".,;:!?\"()")


def _table(words, start):
    return {w: i for i, w in enumerate(words.split(), start)}


EN_UNITS = _table("one two three four five six seven eight nine", 1)
EN_TEENS = _table("ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen", 10)
EN_TENS = {w: i * 10 for i, w in enumerate("twenty thirty forty fifty sixty seventy eighty ninety".split(), 2)}
EN_TENS["fourty"] = 40
EN_SCALES = {"thousand": 1000, "million": 1_000_000}
_EN_WORDS = set(EN_UNITS) | set(EN_TEENS) | set(EN_TENS)


def parse_en(t, i):
    total = cur = 0
    j, last, got = i, None, False
    while j < len(t):
        w = t[j]
        start_ok = last in (None, "hundred", "scale")
        if w in EN_UNITS and (start_ok or last == "tens"):
            cur += EN_UNITS[w]
            last = "unit"
        elif w in EN_TEENS and start_ok:
            cur += EN_TEENS[w]
            last = "teen"
        elif w in EN_TENS and start_ok:
            cur += EN_TENS[w]
            last = "tens"
        elif w == "hundred" and last in (None, "unit", "teen"):
            cur = (cur or 1) * 100
            last = "hundred"
        elif w in EN_SCALES and last in (None, "unit", "teen", "tens", "hundred"):
            total += (cur or 1) * EN_SCALES[w]
            cur = 0
            last = "scale"
        elif w == "and" and last in ("hundred", "scale") and j + 1 < len(t) and t[j + 1] in _EN_WORDS:
            j += 1
            continue
        elif w == "a" and j == i and j + 1 < len(t) and t[j + 1] in ("hundred", "thousand", "million"):
            j += 1
            continue
        else:
            break
        got = True
        j += 1
    return (total + cur, j) if got else None


HA_UNITS = _table("daya biyu uku hudu biyar shida bakwai takwas tara", 1)
HA_TENS = {"ashirin": 20, "talatin": 30, "arbain": 40, "hamsin": 50,
           "sittin": 60, "sabain": 70, "tamanin": 80, "casain": 90}
HA_SCALES = {"miliyan": 1_000_000, "dubu": 1000}


def _ha_tail(t, j):
    n = len(t)
    if j < n and t[j] == "goma":
        if j + 2 < n and t[j + 1] == "sha" and t[j + 2] in HA_UNITS:
            return 10 + HA_UNITS[t[j + 2]], j + 3
        return 10, j + 1
    if j < n and t[j] in HA_TENS:
        v = HA_TENS[t[j]]
        if j + 2 < n and t[j + 1] == "da" and t[j + 2] in HA_UNITS:
            return v + HA_UNITS[t[j + 2]], j + 3
        return v, j + 1
    if j < n and t[j] in HA_UNITS:
        return HA_UNITS[t[j]], j + 1
    return None


def _ha_small(t, i):
    n = len(t)
    if i < n and t[i] == "dari":
        j = i + 1
        mult = 1
        if j < n and t[j] in HA_UNITS:
            mult = HA_UNITS[t[j]]
            j += 1
        total = 100 * mult
        k = j + 1 if j < n and t[j] == "da" else j
        tail = _ha_tail(t, k)
        if tail:
            return total + tail[0], tail[1]
        return total, j
    return _ha_tail(t, i)


def parse_ha(t, i):
    total, j, got = 0, i, False
    while j < len(t):
        if t[j] in HA_SCALES:
            m, k = _ha_small(t, j + 1) or (1, j + 1)
            total += HA_SCALES[t[j]] * m
            j, got = k, True
            if j + 1 < len(t) and t[j] == "da" and (t[j + 1] in HA_SCALES or _ha_small(t, j + 1)):
                j += 1
                continue
            break
        r = _ha_small(t, j)
        if r is None:
            break
        total += r[0]
        j, got = r[1], True
        break
    return (total, j) if got else None


IG_UNITS = {"otu": 1, "abuo": 2, "ato": 3, "ano": 4, "ise": 5,
            "isii": 6, "asaa": 7, "asato": 8, "itoolu": 9}
IG_SCALES = {"nde": 1_000_000, "puku": 1000}


def _ig_small(t, i):
    n = len(t)
    if i < n and t[i] == "iri":
        j = i + 1
        v = 10
        if j < n and t[j] in IG_UNITS and IG_UNITS[t[j]] >= 2:
            v = 10 * IG_UNITS[t[j]]
            j += 1
        if j + 1 < n and t[j] == "na" and t[j + 1] in IG_UNITS:
            return v + IG_UNITS[t[j + 1]], j + 2
        return v, j
    if i < n and t[i] in IG_UNITS:
        return IG_UNITS[t[i]], i + 1
    return None


def _ig_group(t, i):
    n = len(t)
    j, hundreds = i, None
    if j + 1 < n and t[j] in IG_UNITS and t[j + 1] == "nari":
        hundreds, j = IG_UNITS[t[j]] * 100, j + 2
    elif j < n and t[j] == "nari":
        j += 1
        mult = 1
        if j < n and t[j] in IG_UNITS:
            mult = IG_UNITS[t[j]]
            j += 1
        hundreds = 100 * mult
    if hundreds is None:
        return _ig_small(t, i)
    if j + 1 < n and t[j] == "na":
        rest = _ig_small(t, j + 1)
        if rest:
            return hundreds + rest[0], rest[1]
    return hundreds, j


def parse_ig(t, i):
    n = len(t)
    total, j, got = 0, i, False
    while j < n:
        scale_at = j
        mult = None
        if j + 1 < n and t[j] in IG_UNITS and t[j + 1] in IG_SCALES:
            mult, scale_at = IG_UNITS[t[j]], j + 1
        if t[scale_at] in IG_SCALES:
            scale = IG_SCALES[t[scale_at]]
            k = scale_at + 1
            if mult is None:
                m = _ig_small(t, k)
                mult, k = m if m else (1, k)
            total += scale * mult
            j, got = k, True
        else:
            r = _ig_group(t, j)
            if r is None:
                break
            total += r[0]
            j, got = r[1], True
            break
        if j + 1 < n and t[j] == "na" and (t[j + 1] in IG_SCALES or _ig_group(t, j + 1)):
            j += 1
            continue
        break
    return (total, j) if got else None


@lru_cache(maxsize=1)
def _yo_table():
    path = Path(__file__).parent / "data" / "yo_numbers.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def parse_yo(t, i):
    table = _yo_table()
    if i >= len(t) or t[i] not in table:
        return None
    total = prev = table[t[i]]
    j = i + 1
    while j < len(t):
        k = j
        if t[k] == "o" and k + 1 < len(t) and t[k + 1] == "le":
            k += 1
        if t[k] in ("ati", "le") and k + 1 < len(t) and t[k + 1] in table and table[t[k + 1]] < prev:
            prev = table[t[k + 1]]
            total += prev
            j = k + 2
        else:
            break
    return total, j


PARSERS = {"en": [parse_en], "ha": [parse_ha, parse_en], "ig": [parse_ig, parse_en], "yo": [parse_yo, parse_en]}
