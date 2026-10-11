from datetime import date

import readback as rb
from language.schema import default_spec
from normaliser import normalise

SPEC = default_spec("debt_tracker", "en")
REC = {"customer_name": "Mama Ngozi", "amount_owed": 15000, "due_date": "2026-10-16"}


def test_reply_classification():
    assert rb.classify_reply("Yes", "en") == "yes"
    assert rb.classify_reply("not correct", "en") == "no"
    assert rb.classify_reply("daidai ne", "ha") == "yes"
    assert rb.classify_reply("a'a", "ha") == "no"
    assert rb.classify_reply("mba", "ig") == "no"
    assert rb.classify_reply("bẹ́ẹ̀ ni", "yo") == "yes"
    assert rb.classify_reply("hmm", "en") is None
    assert rb.classify_reply("yes no", "en") is None


def test_readback_uses_parsed_values():
    text = rb.readback_text(REC, SPEC, "en")
    assert "₦15,000" in text and "Mama Ngozi" in text and "Friday" in text
    assert "Juma'a" in rb.readback_text(REC, SPEC, "ha")


def test_amount_cross_check():
    heard = normalise("Mama Ngozi owes me fifteen thousand naira", "en").amounts
    assert rb.amounts_disagree(REC, SPEC, heard) == []
    assert rb.amounts_disagree({**REC, "amount_owed": 50000}, SPEC, heard) == ["amount_owed"]


def test_seeded_value_differs():
    assert rb.seed_wrong(REC, SPEC)["amount_owed"] != 15000


def test_saved_values_are_the_read_back_values():
    p = rb.Pending("record", "en", REC, "x", original=REC)
    out = rb.answer(p, "yes")
    assert out.kind == "save" and out.payload == REC


def test_tap_fallback_after_two_failures():
    p = rb.Pending("record", "en", REC, "x", original=REC)
    assert rb.answer(p, "no").kind == "retry"
    assert rb.answer(p, "hmm").kind == "tap"
