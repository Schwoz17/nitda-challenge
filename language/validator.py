import json
from datetime import date

from .schema import (ACTIONS, DIRECTIONS, EDIT_COMMANDS, FIELD_NAME, FIELD_TYPES, LANGUAGES,
                     MAX_FIELDS, NUMERIC, OPERATORS, TEMPLATES)


def parse_output(raw):
    start = raw.find("{")
    if start < 0:
        return None, ["no JSON object in the reply"]
    try:
        obj, _ = json.JSONDecoder().raw_decode(raw[start:])
    except json.JSONDecodeError as exc:
        return None, [f"invalid JSON: {exc.msg}"]
    if not isinstance(obj, dict):
        return None, ["reply must be a JSON object"]
    return obj, []


_BOOLS = {"true": True, "yes": True, "false": False, "no": False}


def tidy(obj, spec):
    if spec and obj.get("action") == "record" and isinstance(obj.get("record"), dict):
        types = _types(spec)
        for key, v in obj["record"].items():
            if types.get(key) == "yes_no" and isinstance(v, str) and v.strip().lower() in _BOOLS:
                obj["record"][key] = _BOOLS[v.strip().lower()]
    edit = obj.get("edit") if obj.get("action") == "edit" else None
    if spec and isinstance(edit, dict) and edit.get("command") == "filter" and isinstance(edit.get("value"), str):
        kind = _types(spec).get(edit.get("field"))
        if kind in NUMERIC:
            try:
                n = float(edit["value"].replace(",", ""))
            except ValueError:
                return obj
            edit["value"] = int(n) if n.is_integer() else n
    return obj


def _types(spec):
    return {f["name"]: f["type"] for f in spec["fields"]}


def _is_number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _is_iso(v):
    try:
        date.fromisoformat(v)
        return True
    except (TypeError, ValueError):
        return False


def check_spec(spec):
    errs = []
    if not isinstance(spec, dict):
        return ["spec must be an object"]
    if spec.get("template") not in TEMPLATES:
        errs.append(f"template must be one of {list(TEMPLATES)}")
    if spec.get("language") not in LANGUAGES:
        errs.append(f"language must be one of {list(LANGUAGES)}")
    fields = spec.get("fields")
    if not isinstance(fields, list) or not fields or len(fields) > MAX_FIELDS:
        return errs + [f"fields must be a list of 1 to {MAX_FIELDS} items"]
    names = []
    for f in fields:
        if isinstance(f, dict) and set(f) != {"name", "type"}:
            errs.append(f"a field has only a name and a type, not {sorted(set(f) - {'name', 'type'})}")
        elif not isinstance(f, dict) or not FIELD_NAME.match(str(f.get("name", ""))):
            errs.append(f"bad field name: {f}")
        elif f.get("type") not in FIELD_TYPES:
            errs.append(f"field {f['name']} has unknown type {f.get('type')}")
        else:
            names.append(f["name"])
    if len(set(names)) != len(names):
        errs.append("field names must be unique")
    if errs:
        return errs
    if spec.get("template") in TEMPLATES:
        missing = [n for n, _ in TEMPLATES[spec["template"]] if n not in names]
        if missing:
            errs.append(f"template fields missing: {missing}")
    types = _types(spec)
    for v in spec.get("views", []):
        if not isinstance(v, dict) or len(v) != 1:
            errs.append(f"bad view: {v}")
        elif "list" in v:
            bad = [n for n in v["list"] if n not in types] if isinstance(v["list"], list) else ["?"]
            if bad:
                errs.append(f"list view uses unknown fields {bad}")
        elif "summary" in v:
            total = v["summary"].get("total") if isinstance(v["summary"], dict) else None
            if types.get(total) not in NUMERIC:
                errs.append("summary total needs a number or money field")
        else:
            errs.append(f"unknown view: {list(v)}")
    for r in spec.get("rules", []):
        if not isinstance(r, dict) or len(r) != 1:
            errs.append(f"bad rule: {r}")
        elif "highlight_past_due" in r:
            if types.get(r["highlight_past_due"]) != "date":
                errs.append("highlight_past_due needs a date field")
        elif "filter" in r:
            errs += check_filter(r["filter"], types)
        elif "sort" in r:
            s = r["sort"]
            if not isinstance(s, dict) or s.get("field") not in types or s.get("direction") not in DIRECTIONS:
                errs.append(f"bad sort rule: {s}")
        else:
            errs.append(f"unknown rule: {list(r)}")
    return errs


def check_filter(f, types):
    if not isinstance(f, dict):
        return ["filter must be an object"]
    field = f.get("field")
    if field not in types:
        return [f"filter field {field} does not exist"]
    if f.get("operator") not in OPERATORS:
        return [f"operator must be one of {list(OPERATORS)}"]
    if types[field] in NUMERIC and not _is_number(f.get("value")):
        return ["filter value must be a number for this field"]
    if "value" not in f:
        return ["filter needs a value"]
    return []


def check_edit(edit, spec):
    if spec is None:
        return ["there is no app to edit yet"]
    if not isinstance(edit, dict) or edit.get("command") not in EDIT_COMMANDS:
        return [f"command must be one of {list(EDIT_COMMANDS)}"]
    types = _types(spec)
    cmd = edit["command"]
    if cmd == "add_field":
        if not FIELD_NAME.match(str(edit.get("name", ""))):
            return ["bad field name"]
        if edit["name"] in types:
            return [f"field {edit['name']} already exists"]
        if edit.get("type") not in FIELD_TYPES:
            return [f"type must be one of {list(FIELD_TYPES)}"]
        if len(types) >= MAX_FIELDS:
            return ["too many fields"]
    elif cmd == "remove_field":
        if edit.get("name") not in types:
            return [f"field {edit.get('name')} does not exist"]
    elif cmd == "rename":
        if edit.get("field") not in types:
            return [f"field {edit.get('field')} does not exist"]
        if not FIELD_NAME.match(str(edit.get("new_name", ""))) or edit["new_name"] in types:
            return ["new_name is invalid or already used"]
    elif cmd == "filter":
        return check_filter(edit, types)
    elif cmd == "sort":
        if edit.get("field") not in types or edit.get("direction") not in DIRECTIONS:
            return ["sort needs an existing field and direction asc or desc"]
    return []


def check_record(record, spec):
    if spec is None:
        return ["there is no app to add records to yet"]
    if not isinstance(record, dict) or not record:
        return ["record must be a non-empty object"]
    types = _types(spec)
    errs = []
    for key, v in record.items():
        t = types.get(key)
        if t is None:
            errs.append(f"unknown field {key}")
        elif t in NUMERIC and (not _is_number(v) or v < 0):
            errs.append(f"{key} must be a non-negative number")
        elif t == "date" and not _is_iso(v):
            errs.append(f"{key} must be an ISO date (YYYY-MM-DD)")
        elif t == "phone" and not (isinstance(v, str) and 7 <= len(v.lstrip("+")) <= 15 and v.lstrip("+").isdigit()):
            errs.append(f"{key} must be a phone number with digits only")
        elif t == "yes_no" and not isinstance(v, bool):
            errs.append(f"{key} must be true or false")
        elif t in ("text", "choice") and not (isinstance(v, str) and v.strip()):
            errs.append(f"{key} must be non-empty text")
    return errs


def validate(obj, spec=None):
    action = obj.get("action")
    if action not in ACTIONS:
        return [f"action must be one of {list(ACTIONS)}"]
    if action in ("ask", "clarify"):
        text = obj.get("text")
        if not isinstance(text, str) or not text.strip() or len(text) > 300:
            return ["text must be a short non-empty string"]
        return []
    if action == "spec":
        return check_spec(obj.get("spec"))
    if action == "edit":
        return check_edit(obj.get("edit"), spec)
    return check_record(obj.get("record"), spec)


def needs_confirmation(obj):
    return obj.get("action") == "edit" and obj["edit"].get("command") == "remove_field"
