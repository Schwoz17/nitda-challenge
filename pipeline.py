from dataclasses import dataclass, field
from datetime import date

import readback as rb
from asr.client import ASRError, Transcript, transcribe
from language.engine import Engine
from language.spec import apply_edit
from normaliser import normalise
from normaliser.dates import mentioned_dates
from store import commit, log_event


@dataclass
class Session:
    spec: dict | None = None
    history: list = field(default_factory=list)
    pending: rb.Pending | None = None
    readbacks: int = 0


class Pipeline:
    def __init__(self, llm, asr=transcribe, seed_every=0, today=date.today):
        self.llm = llm
        self.engine = Engine(llm)
        self.asr = asr
        self.seed_every = seed_every
        self.today = today
        self.sessions = {}

    def turn(self, sid, lang, audio=None, text=None):
        s = self.sessions.setdefault(sid, Session())
        try:
            tr = Transcript(text, lang, "typed", "") if text is not None else self.asr(audio, lang)
        except ASRError as exc:
            out = {"type": "speak", "text": rb.message("repeat", lang)}
            log_event(sid, "asr_error", {"error": str(exc), "audio": str(audio)})
            return out
        norm = normalise(tr.text, lang)
        info = getattr(self.llm, "info", None)
        trace = {
            "input": "typed" if text is not None else "voice", "llm": info() if info else None,
            "lang": lang, "audio": str(audio) if audio else None,
            "asr_model": tr.model, "asr_revision": tr.revision, "transcript": tr.text,
            "normalised": norm.text, "amounts": [a.value for a in norm.amounts],
        }
        out = self._reply(sid, s, lang, tr, trace) if s.pending else self._request(sid, s, lang, norm, trace)
        out["heard"] = tr.text
        log_event(sid, "turn", {**trace, "response": out})
        return out

    def _request(self, sid, s, lang, norm, trace):
        res = self.engine.step(norm.text, lang, s.spec, s.history, self.today())
        trace["engine"] = {"attempts": res.attempts, "raw": res.raw, "errors": res.errors}
        if res.action == "repeat":
            return {"type": "speak", "text": rb.message("repeat", lang)}
        s.history = (s.history + [{"role": "user", "content": norm.text},
                                  {"role": "assistant", "content": res.raw[-1]}])[-6:]
        if res.action in ("ask", "clarify"):
            return {"type": "speak", "text": res.payload["text"]}
        if res.action == "spec":
            s.spec = res.payload["spec"]
            return {"type": "spec", "spec": s.spec}
        if res.action == "edit":
            edit = res.payload["edit"]
            if res.confirm:
                text = rb.message("remove", lang, name=edit["name"])
                s.pending = rb.Pending("edit", lang, edit, text)
                return {"type": "readback", "text": text}
            s.spec = apply_edit(s.spec, edit)
            return {"type": "spec", "spec": s.spec}
        return self._record(sid, s, lang, res.payload["record"], norm, trace)

    def _fix_dates(self, record, spec, text, lang, trace):
        found = mentioned_dates(text, lang, self.today())
        if not found:
            return True
        for f in spec["fields"]:
            name = f["name"]
            if f["type"] != "date" or name not in record:
                continue
            iso = {d.isoformat() for d in found}
            if record[name] in iso:
                continue
            if len(iso) != 1:
                return False
            trace["date_fixed"] = {"from": record[name], "to": next(iter(iso))}
            record[name] = next(iter(iso))
        return True

    def _record(self, sid, s, lang, record, norm, trace):
        if not self._fix_dates(record, s.spec, trace["transcript"], lang, trace):
            return {"type": "speak", "text": rb.message("repeat", lang)}
        if not rb.money_fields(record, s.spec):
            commit(sid, lang, record, {"audio": trace["audio"], "transcript": trace["transcript"]})
            return {"type": "saved", "record": record}
        trace["disagree"] = rb.amounts_disagree(record, s.spec, norm.amounts)
        if trace["disagree"]:
            return {"type": "speak", "text": rb.message("repeat", lang)}
        s.readbacks += 1
        seeded = bool(self.seed_every) and s.readbacks % self.seed_every == 0
        spoken = rb.seed_wrong(record, s.spec) if seeded else record
        text = rb.readback_text(spoken, s.spec, lang)
        s.pending = rb.Pending("record", lang, spoken, text, original=record, seeded=seeded)
        trace["seeded"] = seeded
        return {"type": "readback", "text": text, "record": spoken}

    def _reply(self, sid, s, lang, tr, trace):
        p = s.pending
        out = rb.answer(p, tr.text)
        trace.update(reply=tr.text, verdict=out.verdict, readback=p.text, seeded=p.seeded)
        if out.kind == "save":
            s.pending = None
            if p.kind == "edit":
                s.spec = apply_edit(s.spec, p.spoken)
                return {"type": "spec", "spec": s.spec}
            record = p.original if p.seeded else p.spoken
            commit(sid, lang, record, {"audio": trace["audio"], "transcript": trace["transcript"],
                                       "readback": p.text, "reply": tr.text, "seeded": p.seeded})
            return {"type": "saved", "record": record, "seeded_missed": p.seeded}
        if out.kind == "tap":
            return {"type": "tap", "record": out.payload, "text": p.text}
        if out.kind == "retry" and not p.seeded:
            s.pending = None
            return {"type": "speak", "text": rb.message("retry" if p.kind == "record" else "cancelled", lang)}
        caught = p.seeded and out.kind == "retry"
        if p.kind == "record":
            p.spoken, p.seeded = p.original, False
            p.text = rb.readback_text(p.original, s.spec, lang)
        return {"type": "readback", "text": p.text, "caught": caught}

    def confirm_tap(self, sid, accepted):
        s = self.sessions[sid]
        p, s.pending = s.pending, None
        if not (p and accepted):
            return {"type": "speak", "text": rb.message("repeat", p.lang if p else "en")}
        if p.kind == "edit":
            s.spec = apply_edit(s.spec, p.spoken)
            return {"type": "spec", "spec": s.spec}
        record = p.original or p.spoken
        commit(sid, p.lang, record, {"readback": p.text, "reply": "tap"})
        return {"type": "saved", "record": record}