import json
import re

import service
from asr.client import Transcript
from language.schema import default_spec
from pipeline import Pipeline

HEARD = "Mama Ngozi owes me fifteen thousand naira, she will pay on Friday"


class StandIn:
    def generate(self, messages, max_new_tokens=600):
        system, user = messages[0]["content"], messages[-1]["content"].lower()
        lang = re.search(r'"language":"(\w+)"', system)
        if "There is no app yet" in system:
            return json.dumps({"action": "spec", "spec": default_spec("debt_tracker", lang.group(1) if lang else "en")})
        if "sort" in user:
            return json.dumps({"action": "edit", "edit": {"command": "sort", "field": "due_date", "direction": "asc"}})
        if "notes" in user:
            return json.dumps({"action": "edit", "edit": {"command": "add_field", "name": "notes", "type": "text"}})
        amount = re.search(r"\d+", user)
        name = re.match(r"([a-z' ]+?) (?:owes|tana|ji)", user)
        if amount and name:
            record = {"customer_name": name.group(1).title(), "amount_owed": int(amount.group())}
            return json.dumps({"action": "record", "record": record})
        return json.dumps({"action": "clarify", "text": "Please say it again."})


service._pipeline = Pipeline(StandIn(), asr=lambda path, lang: Transcript(HEARD, lang, "stand-in", ""))
app = service.app