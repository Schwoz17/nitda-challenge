import argparse
import csv
import json
from pathlib import Path

import store
from config import LANGS
from eval.metrics import rate
from language.schema import default_spec

AUDIO = {".ogg", ".opus", ".mp3", ".wav", ".m4a", ".aac", ".mp4"}
FIELDS = ["file", "lang", "transcript", "amounts_found", "result", "readback", "record",
          "amount_ok", "name_ok", "date_ok", "notes"]


def _last_turn(sid):
    path = store.LOG_DIR / f"{sid}.jsonl"
    if not path.exists():
        return {}
    lines = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
    return next((x for x in reversed(lines) if x.get("kind") == "turn"), {})


def run(folder, pipeline, out="voice_results.csv"):
    from pipeline import Session

    rows = []
    for path in sorted(Path(folder).iterdir()):
        if path.suffix.lower() not in AUDIO:
            continue
        lang = path.stem.split("_")[0].lower()
        if lang not in LANGS:
            print("skipped, name must start with ha_, ig_, yo_ or en_:", path.name)
            continue
        sid = path.stem.replace(" ", "-")
        pipeline.sessions[sid] = Session(spec=default_spec("debt_tracker", lang))
        row = dict.fromkeys(FIELDS, "")
        row.update(file=path.name, lang=lang)
        try:
            res = pipeline.turn(sid, lang, audio=str(path))
        except Exception as exc:
            row.update(result="error", notes=str(exc)[:200])
            rows.append(row)
            continue
        turn = _last_turn(sid)
        record = res.get("record")
        row.update(
            transcript=turn.get("transcript", ""),
            amounts_found=" ".join(str(a) for a in turn.get("amounts", [])),
            result=res["type"],
            readback=res.get("text", ""),
            record=json.dumps(record, ensure_ascii=False) if record else "",
            notes="" if turn else "no transcript",
        )
        rows.append(row)
        print(path.name, "->", res["type"])
    with open(out, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return rows


def tally(path):
    by_lang = {}
    with open(path, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            by_lang.setdefault(row["lang"], []).append(row)
    result = {}
    for lang, rows in sorted(by_lang.items()):
        read_back = [r for r in rows if r["result"] in ("readback", "saved", "tap")]
        reviewed = [r for r in read_back if r["amount_ok"].strip().lower() in ("y", "n")]
        correct = sum(r["amount_ok"].strip().lower() == "y" for r in reviewed)
        result[lang] = {
            "interactions": len(rows),
            "read_back": len(read_back),
            "asked_to_repeat_or_failed": len(rows) - len(read_back),
            "reviewed": len(reviewed),
            "amount_correct": rate(correct, len(reviewed)),
        }
    return result


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["tally"])
    ap.add_argument("csv")
    args = ap.parse_args()
    print(json.dumps(tally(args.csv), indent=2, ensure_ascii=False))