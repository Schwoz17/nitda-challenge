from dataclasses import dataclass, field
from datetime import date

from normaliser.numbers import fold

DAYS = {
    "en": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
    "ha": ["Litinin", "Talata", "Laraba", "Alhamis", "Juma'a", "Asabar", "Lahadi"],
    "ig": ["Mọnde", "Tuzdee", "Wenezdee", "Tọọzdee", "Fraịdee", "Satọdee", "Sọndee"],
    "yo": ["Ọjọ́ Ajé", "Ọjọ́ Ìsẹ́gun", "Ọjọ́rú", "Ọjọ́bọ̀", "Ọjọ́ Ẹtì", "Ọjọ́ Àbámẹ́ta", "Ọjọ́ Àìkú"],
}

SENTENCES = {
    "en": ("I heard {amount} for {name}, due {date}. Is that correct?",
           "I heard {amount} for {name}. Is that correct?"),
    "ha": ("Na ji {amount} ga {name}, za a biya ranar {date}. Daidai ne?",
           "Na ji {amount} ga {name}. Daidai ne?"),
    "ig": ("Anụrụ m {amount} maka {name}, ụbọchị ịkwụ ụgwọ bụ {date}. Ọ ziri ezi?",
           "Anụrụ m {amount} maka {name}. Ọ ziri ezi?"),
    "yo": ("Mo gbọ́ {amount} fún {name}, ọjọ́ ìsanwó ni {date}. Ṣé ó tọ́?",
           "Mo gbọ́ {amount} fún {name}. Ṣé ó tọ́?"),
}

MESSAGES = {
    "repeat": {
        "en": "I did not understand. Please say it again.",
        "ha": "Ban gane ba. Don Allah, sake faɗa.",
        "ig": "Aghọtaghị m. Biko, kwuo ya ọzọ.",
        "yo": "N kò gbọ́ yé mi. Jọ̀wọ́, tún sọ ọ́.",
    },
    "retry": {
        "en": "Okay, please say the entry again.",
        "ha": "To, sake faɗar abin.",
        "ig": "Ọ dị mma, biko kwuo ya ọzọ.",
        "yo": "Ó dára, jọ̀wọ́ tún sọ ọ́.",
    },
    "cancelled": {
        "en": "Okay, nothing was changed.",
        "ha": "To, ba a canza komai ba.",
        "ig": "Ọ dị mma, ọ dịghị ihe agbanweela.",
        "yo": "Ó dára, kò sí ohun tí a yí padà.",
    },
    "remove": {
        "en": "Remove {name}? Say yes or no.",
        "ha": "A cire {name}? Ka ce eh ko a'a.",
        "ig": "Wepụ {name}? Sị ee ma ọ bụ mba.",
        "yo": "Yọ {name} kúrò? Sọ bẹ́ẹ̀ ni tàbí bẹ́ẹ̀ kọ́.",
    },
}

_YES = {
    "en": ["yes", "yeah", "yep", "yup", "ok", "okay", "correct", "right", "sure", "na so"],
    "ha": ["eh", "ee", "to", "haka ne", "daidai", "daidai ne", "naam"],
    "ig": ["ee", "eee", "o di mma", "o ziri ezi", "ezi"],
    "yo": ["beeni", "bee ni", "o to", "o dara", "ohun ni"],
}
_NO = {
    "en": ["no", "nope", "wrong", "not correct", "incorrect", "not right"],
    "ha": ["aa", "a a", "ba haka ba", "ba haka bane"],
    "ig": ["mba", "mbanu"],
    "yo": ["beeko", "bee ko", "rara"],
}


def message(kind, lang, **kw):
    return MESSAGES[kind][lang].format(**kw)


def classify_reply(text, lang):
    t = " " + " ".join(fold(w) for w in text.split()) + " "
    no = False
    for p in sorted(_NO["en"] + _NO[lang], key=len, reverse=True):
        if f" {p} " in t:
            no = True
            t = t.replace(f" {p} ", " ")
    yes = any(f" {p} " in t for p in _YES["en"] + _YES[lang])
    if yes == no:
        return None
    return "yes" if yes else "no"


def money_fields(record, spec):
    types = {f["name"]: f["type"] for f in spec["fields"]}
    return [k for k in record if types.get(k) == "money"]


def amounts_disagree(record, spec, amounts):
    heard = {a.value for a in amounts}
    return [k for k in money_fields(record, spec) if record[k] not in heard]


def _fmt_amount(v):
    return f"₦{v:,.0f}" if float(v).is_integer() else f"₦{v:,.2f}"


def _fmt_date(iso, lang):
    d = date.fromisoformat(iso)
    return f"{DAYS[lang][d.weekday()]}, {d.day:02d}/{d.month:02d}/{d.year}"


def readback_text(record, spec, lang):
    types = {f["name"]: f["type"] for f in spec["fields"]}
    money = next((record[k] for k in record if types[k] == "money"), None)
    name = next((record[k] for k in record if types[k] == "text"), None)
    due = next((record[k] for k in record if types[k] == "date"), None)
    if money is None or name is None:
        return "; ".join(f"{k}: {v}" for k, v in record.items())
    with_date, without = SENTENCES[lang]
    if due:
        return with_date.format(amount=_fmt_amount(money), name=name, date=_fmt_date(due, lang))
    return without.format(amount=_fmt_amount(money), name=name)


def seed_wrong(record, spec):
    wrong = dict(record)
    key = money_fields(record, spec)[0]
    v = record[key]
    wrong[key] = int(round(v * 1.5 / 500) * 500) if v else 5000
    if wrong[key] == v:
        wrong[key] = v + 5000
    return wrong


@dataclass
class Pending:
    kind: str
    lang: str
    spoken: dict
    text: str
    original: dict | None = None
    seeded: bool = False
    attempts: int = 0


@dataclass
class Outcome:
    kind: str
    payload: dict = field(default_factory=dict)
    verdict: str | None = None


def answer(p, reply):
    verdict = classify_reply(reply, p.lang)
    if verdict == "yes":
        return Outcome("save", p.spoken, verdict)
    p.attempts += 1
    if p.attempts >= 2:
        return Outcome("tap", p.original or p.spoken, verdict)
    return Outcome("retry" if verdict == "no" else "unclear", p.original or p.spoken, verdict)