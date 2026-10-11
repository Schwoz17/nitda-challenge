import pytest

from normaliser import normalise


def values(text, lang):
    return [a.value for a in normalise(text, lang).amounts]


@pytest.mark.parametrize("text,expected", [
    ("Mama Ngozi owes me ₦15,000 she will pay Friday", [15000]),
    ("fifteen thousand five hundred naira", [15500]),
    ("one hundred and fifty", [150]),
    ("she owes 15k", [15000]),
    ("N20000 and twenty five thousand", [20000, 25000]),
    ("a thousand naira", [1000]),
])
def test_english(text, expected):
    assert values(text, "en") == expected


@pytest.mark.parametrize("text,expected", [
    ("naira dubu goma sha biyar", [15000]),
    ("dubu ɗaya da ɗari biyar", [1500]),
    ("dubu ashirin da biyar", [25000]),
    ("dubu ɗari biyu", [200000]),
    ("ɗari da hamsin", [150]),
    ("ta ce za ta biya ɗari biyar", [500]),
])
def test_hausa(text, expected):
    assert values(text, "ha") == expected


@pytest.mark.parametrize("text,expected", [
    ("puku iri na ise", [15000]),
    ("puku otu na narị ise", [1500]),
    ("iri abụọ na ise", [25]),
    ("narị abụọ", [200]),
    ("otu puku", [1000]),
])
def test_igbo(text, expected):
    assert values(text, "ig") == expected


def test_yoruba_table_and_connector():
    assert values("ogún ati eta", "yo") == [23]
    assert values("ẹgbẹ̀rún ati ẹ̀ẹ́dẹ́gbẹ̀ta", "yo") == [1500]


def test_code_switching():
    assert values("naira fifteen thousand", "ha") == [15000]


def test_text_is_rewritten_with_digits_and_positions_match():
    n = normalise("owes fifteen thousand naira today", "en")
    assert n.text == "owes 15000 naira today"
    a = n.amounts[0]
    assert n.text[a.start:a.end] == "15000"
    assert a.money


def test_names_are_untouched():
    n = normalise("Adaeze Okonkwo owes me 5k", "ig")
    assert n.text.startswith("Adaeze Okonkwo")


def test_homographs_are_not_numbers_without_money_context():
    assert values("àti ìgbà tí wọ́n máa san", "yo") == []
    assert values("otu nwoke bịara", "ig") == []
    assert values("naira dubu", "ha") == [1000]
    assert normalise("àti ìgbà tí wọ́n máa san", "yo").text == "àti ìgbà tí wọ́n máa san"
