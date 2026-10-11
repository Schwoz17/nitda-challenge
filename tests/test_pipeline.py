import json
from datetime import date

import pytest

import config
import store
from pipeline import Pipeline


class FakeLLM:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def generate(self, messages, max_new_tokens=600):
        self.calls.append(messages)
        return self.replies.pop(0)


@pytest.fixture(autouse=True)
def tmp_storage(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "t.db")
    monkeypatch.setattr(store, "LOG_DIR", tmp_path / "logs")


def j(obj):
    return json.dumps(obj)


def spec_reply():
    from language.schema import default_spec
    return j({"action": "spec", "spec": default_spec("debt_tracker", "en")})


def record_reply(amount=15000):
    return j({"action": "record", "record": {"customer_name": "Mama Ngozi", "amount_owed": amount, "due_date": "2026-10-16"}})


def make(replies, **kw):
    llm = FakeLLM(replies)
    kw.setdefault("today", lambda: date(2026, 10, 11))
    return Pipeline(llm, **kw), llm


def test_create_record_confirm_flow():
    p, _ = make([spec_reply(), record_reply()])
    assert p.turn("s", "en", text="I sell fabric, I need to track debts")["type"] == "spec"
    out = p.turn("s", "en", text="Mama Ngozi owes me fifteen thousand naira, pay Friday")
    assert out["type"] == "readback" and "₦15,000" in out["text"]
    out = p.turn("s", "en", text="yes")
    assert out["type"] == "saved" and out["record"]["amount_owed"] == 15000


def test_amount_mismatch_never_reaches_readback():
    p, _ = make([spec_reply(), record_reply(50000)])
    p.turn("s", "en", text="debt tracker please")
    out = p.turn("s", "en", text="Mama Ngozi owes me fifteen thousand naira")
    assert out["type"] == "speak"
    assert p.sessions["s"].pending is None


def test_invalid_output_is_retried_then_asks_to_repeat():
    p, llm = make(["nonsense", "still nonsense", "nope"])
    out = p.turn("s", "en", text="hello")
    assert out["type"] == "speak" and len(llm.calls) == 3


def test_invalid_then_valid_recovers():
    p, llm = make(["oops", spec_reply()])
    assert p.turn("s", "en", text="debt tracker")["type"] == "spec"
    assert len(llm.calls) == 2


def test_remove_field_waits_for_confirmation():
    p, _ = make([spec_reply(), j({"action": "edit", "edit": {"command": "remove_field", "name": "phone"}})])
    p.turn("s", "en", text="debt tracker")
    assert p.turn("s", "en", text="remove phone")["type"] == "readback"
    assert any(f["name"] == "phone" for f in p.sessions["s"].spec["fields"])
    assert p.turn("s", "en", text="yes")["type"] == "spec"
    assert not any(f["name"] == "phone" for f in p.sessions["s"].spec["fields"])


def test_seeded_readback_rejected_then_reads_correct_value():
    p, _ = make([spec_reply(), record_reply()], seed_every=1)
    p.turn("s", "en", text="debt tracker")
    first = p.turn("s", "en", text="Mama Ngozi owes me fifteen thousand naira")
    assert "₦15,000" not in first["text"]
    second = p.turn("s", "en", text="no")
    assert second["caught"] and "₦15,000" in second["text"]
    assert p.turn("s", "en", text="yes")["record"]["amount_owed"] == 15000


def test_asr_failure_asks_to_repeat():
    from asr.client import ASRError

    def broken(audio, lang):
        raise ASRError("down")

    p = Pipeline(FakeLLM([]), asr=broken)
    assert p.turn("s", "ha", audio="x.wav")["type"] == "speak"


def test_weekday_in_speech_overrides_wrong_model_date():
    p, _ = make([spec_reply(), j({"action": "record", "record": {
        "customer_name": "Mama Ngozi", "amount_owed": 15000, "due_date": "2026-10-11"}})])
    p.turn("s", "en", text="debt tracker")
    out = p.turn("s", "en", text="Mama Ngozi owes me fifteen thousand naira, she will pay Friday")
    assert out["record"]["due_date"] == "2026-10-16"
    assert "Friday" in out["text"]


def test_edit_prompt_shows_every_command():
    from language.prompts import build_messages
    from language.schema import default_spec as ds
    system = build_messages("en", "x", ds("debt_tracker", "en"), [], date(2026, 10, 11), len, 10**6)[0]["content"]
    for cmd in ("add_field", "remove_field", "rename", "filter", "sort"):
        assert f'"command":"{cmd}"' in system
    assert "record" not in build_messages("en", "x", None, [], date(2026, 10, 11), len, 10**6)[0]["content"].split("Example.")[0].split("Your reply must be one of:")[1]


def test_retries_use_a_higher_temperature_and_restore_it():
    class Warm(FakeLLM):
        temperature = 0.1
        temps = []

        def generate(self, messages, max_new_tokens=600):
            self.temps.append(self.temperature)
            return super().generate(messages, max_new_tokens)

    llm = Warm(["bad", "worse", spec_reply()])
    p = Pipeline(llm, today=lambda: date(2026, 10, 11))
    assert p.turn("s", "en", text="debt tracker")["type"] == "spec"
    assert llm.temps == [0.1, 0.4, 0.7] and llm.temperature == 0.1
