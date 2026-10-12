import json
import tempfile
from datetime import date
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
pytest.importorskip("multipart")

from fastapi.testclient import TestClient

import service
import store
from asr.client import Transcript
from language.schema import default_spec
from pipeline import Pipeline


class FakeLLM:
    def __init__(self):
        self.replies = [
            json.dumps({"action": "spec", "spec": default_spec("debt_tracker", "en")}),
            json.dumps({"action": "record", "record": {"customer_name": "Mama Ngozi", "amount_owed": 15000, "due_date": "2026-10-11"}}),
        ]

    def generate(self, messages, max_new_tokens=600):
        return self.replies.pop(0)


@pytest.fixture
def client(monkeypatch):
    tmp = Path(tempfile.mkdtemp())
    monkeypatch.setattr(store, "DB_PATH", tmp / "t.db")
    monkeypatch.setattr(store, "LOG_DIR", tmp / "logs")
    heard = "Mama Ngozi owes me fifteen thousand naira, she will pay Friday"
    monkeypatch.setattr(service, "_pipeline", Pipeline(
        FakeLLM(), asr=lambda path, lang: Transcript(heard, lang, "fake", ""), today=lambda: date(2026, 10, 11)))
    return TestClient(service.app)


def test_full_voice_flow(client):
    sid = client.post("/session").json()["session"]
    assert client.post("/turn", data={"session": sid, "lang": "en", "text": "debt tracker"}).json()["type"] == "spec"
    out = client.post("/turn", data={"session": sid, "lang": "en"}, files={"audio": ("clip.ogg", b"x", "audio/ogg")}).json()
    assert out["type"] == "readback" and "16/10/2026" in out["text"]
    assert client.post("/turn", data={"session": sid, "lang": "en", "text": "yes"}).json()["type"] == "saved"


def test_bad_requests(client):
    assert client.post("/turn", data={"session": "s", "lang": "xx", "text": "hi"}).status_code == 400
    assert client.post("/turn", data={"session": "s", "lang": "en"}).status_code == 400
    assert client.post("/tap", data={"session": "nope", "accepted": "true"}).status_code == 404


def test_browser_calls_from_another_origin_are_allowed(client):
    r = client.options("/turn", headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "POST"})
    assert r.status_code == 200 and r.headers["access-control-allow-origin"] in ("*", "http://localhost:3000")


def test_health_reports_readiness(client):
    body = client.get("/health").json()
    assert body["ok"] is True and body["model_ready"] is True and body["asr_ready"] in (True, False)