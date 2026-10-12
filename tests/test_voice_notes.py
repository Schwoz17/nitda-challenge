import csv
import json
from datetime import date

import store
from asr.client import Transcript
from language.schema import default_spec
from pipeline import Pipeline
from scripts.voice_notes import run, tally
from pathlib import Path


class FakeLLM:
    def generate(self, messages, max_new_tokens=600):
        return json.dumps({"action": "record", "record": {"customer_name": "Mama Ngozi", "amount_owed": 15000}})


def test_run_and_tally(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "t.db")
    monkeypatch.setattr(store, "LOG_DIR", tmp_path / "logs")
    folder = tmp_path / "notes"
    folder.mkdir()
    for name in ("ha_01.ogg", "ha_02.ogg", "xx_01.ogg", "readme.txt"):
        (folder / name).write_bytes(b"x")
    heard = {"ha_01": "Mama Ngozi tana bina naira dubu goma sha biyar", "ha_02": "hmm"}
    asr = lambda path, lang: Transcript(heard[Path(path).stem], lang, "fake", "")
    p = Pipeline(FakeLLM(), asr=asr, today=lambda: date(2026, 10, 11))
    out = tmp_path / "r.csv"
    rows = run(folder, p, str(out))
    assert [r["file"] for r in rows] == ["ha_01.ogg", "ha_02.ogg"]
    assert rows[0]["result"] == "readback" and "15,000" in rows[0]["readback"]
    assert rows[1]["result"] == "speak"

    with open(out, encoding="utf-8-sig", newline="") as f:
        data = list(csv.DictReader(f))
    data[0]["amount_ok"] = "y"
    with open(out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, data[0].keys())
        w.writeheader()
        w.writerows(data)
    t = tally(str(out))["ha"]
    assert t["interactions"] == 2 and t["read_back"] == 1 and t["reviewed"] == 1
    assert t["amount_correct"]["rate"] == 1.0