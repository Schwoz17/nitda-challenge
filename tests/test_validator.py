import json

from language.schema import default_spec
from language.spec import apply_edit
from language.validator import check_edit, check_record, needs_confirmation, parse_output, tidy, validate


def spec():
    return default_spec("debt_tracker", "ha")


def test_default_specs_are_valid():
    for t in ("debt_tracker", "inventory", "bookings"):
        assert validate({"action": "spec", "spec": default_spec(t, "en")}) == []


def test_parse_output_ignores_surrounding_text():
    obj, errs = parse_output('Sure! {"action":"ask","text":"Who do you sell to?"} done')
    assert not errs and obj["action"] == "ask"
    assert parse_output("no json")[0] is None


def test_spec_missing_template_field():
    s = spec()
    s["fields"] = [f for f in s["fields"] if f["name"] != "amount_owed"]
    assert validate({"action": "spec", "spec": s})


def test_record_checks():
    s = spec()
    ok = {"customer_name": "Mama Ngozi", "amount_owed": 15000, "due_date": "2026-10-16"}
    assert check_record(ok, s) == []
    assert check_record({**ok, "amount_owed": "15000"}, s)
    assert check_record({**ok, "due_date": "Friday"}, s)
    assert check_record({**ok, "colour": "red"}, s)
    assert check_record({**ok, "amount_owed": -5}, s)


def test_edit_checks():
    s = spec()
    assert check_edit({"command": "add_field", "name": "notes", "type": "text"}, s) == []
    assert check_edit({"command": "add_field", "name": "phone", "type": "phone"}, s)
    assert check_edit({"command": "filter", "field": "amount_owed", "operator": "greater_than", "value": 20000}, s) == []
    assert check_edit({"command": "filter", "field": "amount_owed", "operator": "greater_than", "value": "lots"}, s)
    assert check_edit({"command": "sort", "field": "due_date", "direction": "asc"}, s) == []
    assert check_edit({"command": "sort", "field": "nope", "direction": "asc"}, s)
    assert check_edit({"command": "rename", "field": "paid", "new_name": "settled"}, s) == []


def test_remove_needs_confirmation():
    obj = {"action": "edit", "edit": {"command": "remove_field", "name": "phone"}}
    assert validate(obj, spec()) == [] and needs_confirmation(obj)


def test_apply_edit_keeps_spec_valid():
    s = spec()
    s = apply_edit(s, {"command": "add_field", "name": "notes", "type": "text"})
    s = apply_edit(s, {"command": "filter", "field": "amount_owed", "operator": "greater_than", "value": 20000})
    s = apply_edit(s, {"command": "sort", "field": "due_date", "direction": "desc"})
    s = apply_edit(s, {"command": "sort", "field": "customer_name", "direction": "asc"})
    s = apply_edit(s, {"command": "rename", "field": "due_date", "new_name": "pay_by"})
    assert sum("sort" in r for r in s["rules"]) == 1
    assert {"highlight_past_due": "pay_by"} in s["rules"]
    assert any(f["name"] == "notes" for f in s["fields"])
    json.dumps(s)


def test_tidy_turns_numeric_string_into_number_for_numeric_fields_only():
    s = spec()
    obj = {"action": "edit", "edit": {"command": "filter", "field": "amount_owed", "operator": "greater_than", "value": "20,000"}}
    assert validate(tidy(obj, s), s) == [] and obj["edit"]["value"] == 20000
    text = {"action": "edit", "edit": {"command": "filter", "field": "customer_name", "operator": "equals", "value": "20000"}}
    assert tidy(text, s)["edit"]["value"] == "20000"


def test_tidy_turns_yes_no_text_into_booleans():
    s = spec()
    obj = {"action": "record", "record": {"customer_name": "Mama Ngozi", "amount_owed": 15000, "paid": "no"}}
    assert validate(tidy(obj, s), s) == [] and obj["record"]["paid"] is False


def test_fields_with_extra_keys_are_rejected():
    s = spec()
    s["fields"][0]["value"] = "Mama Ngozi"
    assert validate({"action": "spec", "spec": s})
