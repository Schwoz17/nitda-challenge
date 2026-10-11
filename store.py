import json
import sqlite3
import time

from config import DB_PATH, LOG_DIR


def log_event(session, kind, data):
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    line = {"ts": time.time(), "session": session, "kind": kind, **data}
    with open(LOG_DIR / f"{session}.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(line, ensure_ascii=False, default=str) + "\n")


def _db():
    con = sqlite3.connect(DB_PATH)
    con.execute(
        "create table if not exists records ("
        "id integer primary key, created real, session text, lang text, record text, "
        "audio text, transcript text, readback text, reply text, seeded integer)"
    )
    return con


def commit(session, lang, record, evidence):
    with _db() as con:
        cur = con.execute(
            "insert into records (created, session, lang, record, audio, transcript, readback, reply, seeded) "
            "values (?,?,?,?,?,?,?,?,?)",
            (time.time(), session, lang, json.dumps(record, ensure_ascii=False),
             evidence.get("audio"), evidence.get("transcript"), evidence.get("readback"),
             evidence.get("reply"), int(evidence.get("seeded", False))),
        )
    return cur.lastrowid
