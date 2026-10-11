from datetime import timedelta

from .numbers import fold

WEEKDAYS = {
    "en": ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"],
    "ha": ["litinin", "talata", "laraba", "alhamis", "jumaa", "asabar", "lahadi"],
    "ig": ["monde", "tuzdee", "wenezdee", "toozdee", "fraidee", "satodee", "sondee"],
    "yo": ["ojo aje", "ojo isegun", "ojoru", "ojobo", "ojo eti", "ojo abameta", "ojo aiku"],
}
RELATIVE = {"today": 0, "tomorrow": 1}


def mentioned_dates(text, lang, today):
    padded = " " + " ".join(fold(w) for w in text.split()) + " "
    found = set()
    for code in {"en", lang}:
        for i, name in enumerate(WEEKDAYS[code]):
            if f" {name} " in padded:
                found.add(today + timedelta(days=(i - today.weekday()) % 7 or 7))
    for word, offset in RELATIVE.items():
        if f" {word} " in padded:
            found.add(today + timedelta(days=offset))
    return found
