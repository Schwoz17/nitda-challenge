import re
import unicodedata
from dataclasses import dataclass

from .numbers import PARSERS, fold, parse_en

CURRENCY = {"naira", "kobo", "ngn", "n"}
_DIGITS = re.compile(
    r"(?<![\w.,])(?P<cur>₦|N(?=\d)|NGN\s?)?(?P<num>\d{1,3}(?:,\d{3})+|\d+)"
    r"(?P<dec>\.\d+)?(?P<suf>[kKmM](?![^\W\d_]))?"
)
_TOKEN = re.compile(r"[^\s.,;:!?\"()]+")
_SUFFIX = {"k": 1000, "m": 1_000_000}


@dataclass
class Amount:
    value: float
    start: int
    end: int
    raw: str
    money: bool


@dataclass
class Normalised:
    text: str
    amounts: list


def _num(v):
    return int(v) if float(v).is_integer() else float(v)


def _digit_spans(text):
    spans = []
    for m in _DIGITS.finditer(text):
        value = float(m.group("num").replace(",", "") + (m.group("dec") or ""))
        suf = m.group("suf")
        if suf:
            value *= _SUFFIX[suf.lower()]
        prev = re.findall(r"\w+", text[: m.start()])[-1:]
        nxt = re.findall(r"\w+", text[m.end():])[:1]
        near = any(fold(w) in CURRENCY for w in prev + nxt)
        spans.append((m.start(), m.end(), _num(value), m.group(0), bool(m.group("cur") or suf or near)))
    return spans


def _near_currency(words, i, j):
    return bool({words[x] for x in (i - 1, j) if 0 <= x < len(words)} & CURRENCY)


def _word_spans(text, lang, taken):
    toks = []
    for m in _TOKEN.finditer(text):
        if any(m.start() < e and s < m.end() for s, e, *_ in taken):
            continue
        f = fold(m.group(0))
        if f and not re.search(r"\d", f):
            toks.append((m.start(), m.end(), f))
    words = [f for _, _, f in toks]
    spans, i = [], 0
    while i < len(toks):
        best = None
        for parse in PARSERS[lang]:
            r = parse(words, i)
            if not r:
                continue
            if parse is not parse_en and r[1] - i == 1 and not _near_currency(words, i, r[1]):
                continue
            if best is None or r[1] > best[1]:
                best = r
        if not best:
            i += 1
            continue
        value, j = best
        if j < len(words) and words[j] == "k":
            value, j = value * 1000, j + 1
        spans.append((toks[i][0], toks[j - 1][1], _num(value), text[toks[i][0]:toks[j - 1][1]], _near_currency(words, i, j)))
        i = j
    return spans


def normalise(text, lang):
    text = unicodedata.normalize("NFC", text).strip()
    digits = _digit_spans(text)
    spans = sorted(digits + _word_spans(text, lang, digits))
    out, amounts, pos = [], [], 0
    cursor = 0
    for start, end, value, raw, money in spans:
        out.append(text[pos:start])
        cursor += start - pos
        rep = str(value)
        amounts.append(Amount(value, cursor, cursor + len(rep), raw, money))
        out.append(rep)
        cursor += len(rep)
        pos = end
    out.append(text[pos:])
    return Normalised("".join(out), amounts)
