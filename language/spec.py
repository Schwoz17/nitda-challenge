import copy


def apply_edit(spec, edit):
    new = copy.deepcopy(spec)
    cmd = edit["command"]
    if cmd == "add_field":
        new["fields"].append({"name": edit["name"], "type": edit["type"]})
        for v in new["views"]:
            if "list" in v:
                v["list"].append(edit["name"])
    elif cmd == "remove_field":
        name = edit["name"]
        new["fields"] = [f for f in new["fields"] if f["name"] != name]
        for v in new["views"]:
            if "list" in v:
                v["list"] = [n for n in v["list"] if n != name]
        new["views"] = [v for v in new["views"] if v.get("summary", {}).get("total") != name]
        new["rules"] = [r for r in new["rules"] if not _uses(r, name)]
    elif cmd == "rename":
        old, fresh = edit["field"], edit["new_name"]
        for f in new["fields"]:
            if f["name"] == old:
                f["name"] = fresh
        for v in new["views"]:
            if "list" in v:
                v["list"] = [fresh if n == old else n for n in v["list"]]
            elif v.get("summary", {}).get("total") == old:
                v["summary"]["total"] = fresh
        new["rules"] = [_renamed(r, old, fresh) for r in new["rules"]]
    elif cmd in ("filter", "sort"):
        new["rules"] = [r for r in new["rules"] if cmd not in r]
        body = {k: v for k, v in edit.items() if k != "command"}
        new["rules"].append({cmd: body})
    return new


def _uses(rule, name):
    (key, val), = rule.items()
    if key == "highlight_past_due":
        return val == name
    return val.get("field") == name


def _renamed(rule, old, fresh):
    (key, val), = rule.items()
    if key == "highlight_past_due":
        return {key: fresh if val == old else val}
    return {key: {**val, "field": fresh if val.get("field") == old else val.get("field")}}
