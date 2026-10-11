from datetime import date

from normaliser.dates import mentioned_dates

SUNDAY = date(2026, 10, 11)


def test_english_weekday_is_next_occurrence():
    assert mentioned_dates("she will pay Friday", "en", SUNDAY) == {date(2026, 10, 16)}


def test_same_weekday_means_next_week():
    assert mentioned_dates("pay on Sunday", "en", SUNDAY) == {date(2026, 10, 18)}


def test_local_weekdays():
    assert mentioned_dates("za ta biya ranar Juma'a", "ha", SUNDAY) == {date(2026, 10, 16)}
    assert mentioned_dates("ọjọ́ Ẹtì ni", "yo", SUNDAY) == {date(2026, 10, 16)}
    assert mentioned_dates("Fraịdee", "ig", SUNDAY) == {date(2026, 10, 16)}


def test_tomorrow_and_no_date():
    assert mentioned_dates("tomorrow", "en", SUNDAY) == {date(2026, 10, 12)}
    assert mentioned_dates("Mama Ngozi owes me money", "en", SUNDAY) == set()
