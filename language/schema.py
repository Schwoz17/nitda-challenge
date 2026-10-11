import re

LANGUAGES = ("ha", "ig", "yo", "en")
FIELD_TYPES = ("text", "number", "money", "date", "phone", "choice", "yes_no")
OPERATORS = ("equals", "greater_than", "less_than")
DIRECTIONS = ("asc", "desc")
EDIT_COMMANDS = ("add_field", "remove_field", "rename", "filter", "sort")
ACTIONS = ("ask", "clarify", "spec", "edit", "record")
NUMERIC = ("number", "money")

TEMPLATES = {
    "debt_tracker": [
        ("customer_name", "text"), ("phone", "phone"), ("amount_owed", "money"),
        ("due_date", "date"), ("paid", "yes_no"),
    ],
    "inventory": [
        ("item", "text"), ("quantity", "number"), ("unit_price", "money"),
        ("low_stock_level", "number"),
    ],
    "bookings": [
        ("customer", "text"), ("service", "text"), ("date_time", "date"), ("status", "choice"),
    ],
}

FIELD_NAME = re.compile(r"^[a-z][a-z0-9_]{0,31}$")
MAX_FIELDS = 12


def default_spec(template, lang):
    fields = [{"name": n, "type": t} for n, t in TEMPLATES[template]]
    money = next((f["name"] for f in fields if f["type"] == "money"), None)
    date = next((f["name"] for f in fields if f["type"] == "date"), None)
    shown = [f["name"] for f in fields][:3] if template == "debt_tracker" else [f["name"] for f in fields]
    views = [{"list": shown}]
    rules = []
    if money:
        views.append({"summary": {"total": money}})
    if template == "debt_tracker" and date:
        rules.append({"highlight_past_due": date})
    return {"template": template, "language": lang, "fields": fields, "views": views, "rules": rules}
