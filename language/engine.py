from dataclasses import dataclass, field
from datetime import date

from config import PROMPT_TOKEN_BUDGET

from .prompts import build_messages, retry_message
from .validator import needs_confirmation, parse_output, tidy, validate

MAX_RETRIES = 2


@dataclass
class Result:
    action: str
    payload: dict = field(default_factory=dict)
    confirm: bool = False
    attempts: int = 1
    raw: list = field(default_factory=list)
    errors: list = field(default_factory=list)


def _approx(text):
    return len(text) // 3 + 1


class Engine:
    def __init__(self, llm):
        self.llm = llm
        self.count = getattr(llm, "count_tokens", _approx)

    def step(self, utterance, lang, spec=None, history=(), today=None):
        today = today or date.today()
        messages = build_messages(lang, utterance, spec, history, today, self.count, PROMPT_TOKEN_BUDGET)
        raw_log, errors = [], []
        base = getattr(self.llm, "temperature", None)
        try:
            return self._run(messages, spec, base, raw_log)
        finally:
            if base is not None:
                self.llm.temperature = base

    def _run(self, messages, spec, base, raw_log):
        errors = []
        for attempt in range(1, MAX_RETRIES + 2):
            if base is not None:
                self.llm.temperature = min(base + 0.3 * (attempt - 1), 0.8)
            raw = self.llm.generate(messages)
            raw_log.append(raw)
            obj, errors = parse_output(raw)
            if obj is not None:
                errors = validate(tidy(obj, spec), spec)
            if not errors:
                return Result(obj["action"], obj, needs_confirmation(obj), attempt, raw_log)
            messages = messages + [{"role": "assistant", "content": raw}, retry_message(errors)]
        return Result("repeat", {}, False, MAX_RETRIES + 1, raw_log, errors)