import json

from config import LANG_NAMES

HEAD = """You are the language engine of Magana, a voice app builder for Nigerian traders. The user speaks {language}. Answer with ONE JSON object and nothing else.

Use only names, amounts and dates the user actually said. Never invent them. If anything is unclear, use clarify. Use no technical words in questions. Amounts are plain numbers in naira, dates are ISO (YYYY-MM-DD), and numbers in the user's text are already written as digits.
Today is {today}.
"""

NO_APP = """
There is no app yet. Your reply must be one of:
{{"action":"spec","spec":{{...}}}}  build the app the user describes
{{"action":"ask","text":"one short plain question in {language}"}}  if you need one more detail
{{"action":"clarify","text":"ask the user to repeat, in {language}"}}  if you did not understand

Templates: debt_tracker (who owes money), inventory (stock), bookings (appointments). A spec must keep its template's fields:
debt_tracker = customer_name, phone, amount_owed, due_date, paid
inventory = item, quantity, unit_price, low_stock_level
bookings = customer, service, date_time, status

Example. User: "I run a provisions shop and people buy on credit, I want to track them."
{{"action":"spec","spec":{{"template":"debt_tracker","language":"{lang}","fields":[{{"name":"customer_name","type":"text"}},{{"name":"phone","type":"phone"}},{{"name":"amount_owed","type":"money"}},{{"name":"due_date","type":"date"}},{{"name":"paid","type":"yes_no"}}],"views":[{{"list":["customer_name","amount_owed","due_date"]}},{{"summary":{{"total":"amount_owed"}}}}],"rules":[{{"highlight_past_due":"due_date"}}]}}}}
"""

WITH_APP = """
The app already exists. Your reply must be one of:
{{"action":"record","record":{{"customer_name":"<name the user said>","amount_owed":<number the user said>,"due_date":"<YYYY-MM-DD>"}}}}  the user is adding an entry. Include only the fields the user mentioned, and write yes/no fields as JSON true or false, never as text.
{{"action":"edit","edit":{{...}}}}  the user wants to change the app (see below)
{{"action":"ask","text":"one short plain question in {language}"}}
{{"action":"clarify","text":"ask the user to repeat, in {language}"}}

Changes always use the action "edit", with the command inside "edit". Never repeat the whole spec to make a change. Examples:
{{"action":"edit","edit":{{"command":"add_field","name":"<new field name>","type":"<field type>"}}}}
{{"action":"edit","edit":{{"command":"remove_field","name":"<field name>"}}}}
{{"action":"edit","edit":{{"command":"rename","field":"<field name>","new_name":"<new name>"}}}}
{{"action":"edit","edit":{{"command":"filter","field":"<field name>","operator":"greater_than","value":<number the user said>}}}}  operator is equals, greater_than or less_than
{{"action":"edit","edit":{{"command":"sort","field":"<field name>","direction":"asc"}}}}  direction is asc or desc
Field types: text, number, money, date, phone, choice, yes_no. Use the field names in the current spec.
Current app spec: {spec}
"""


def build_messages(lang, utterance, spec, history, today, count, budget):
    body = WITH_APP.format(language=LANG_NAMES[lang], spec=json.dumps(spec, ensure_ascii=False)) if spec \
        else NO_APP.format(language=LANG_NAMES[lang], lang=lang)
    system = HEAD.format(language=LANG_NAMES[lang], today=today.isoformat()) + body
    turns = list(history)
    user = {"role": "user", "content": utterance}
    while turns and count(system) + sum(count(m["content"]) for m in turns) + count(utterance) > budget:
        turns.pop(0)
    return [{"role": "system", "content": system}, *turns, user]


def retry_message(errors):
    return {"role": "user", "content": "That reply was not valid: " + "; ".join(errors) + ". Answer again with one valid JSON object in the formats you were given."}