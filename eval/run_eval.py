import argparse
import json
from datetime import date
from pathlib import Path

from eval import metrics
from normaliser import normalise

HERE = Path(__file__).parent


def read(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def run_numbers(rows, lang):
    hits = sum(
        [a.value for a in normalise(r["text"], lang).amounts] == r["values"] for r in rows
    )
    return {"exact_match": metrics.rate(hits, len(rows))}


def run_asr(rows, lang, terms):
    from asr.client import transcribe

    pairs = [(r["reference"], transcribe(r["audio"], lang).text) for r in rows]
    return {
        "wer": round(metrics.wer(pairs), 4),
        "number_error_rate": round(metrics.number_error_rate(pairs, lang), 4),
        "business_term_recall": metrics.term_recall(pairs, terms),
        "n": len(pairs),
    }


def run_spec(rows, lang):
    from language.engine import Engine
    from language.model import NAtlasLLM

    engine = Engine(NAtlasLLM())
    hits = first_try = 0
    for r in rows:
        res = engine.step(normalise(r["utterance"], lang).text, lang, None, [], date.today())
        ok = res.action == "spec" and metrics.spec_matches(res.payload["spec"], r["expected"])
        hits += ok
        first_try += ok and res.attempts == 1
    return {"spec_accuracy": metrics.rate(hits, len(rows)), "first_attempt": metrics.rate(first_try, len(rows))}


def run_edits(rows, lang):
    from language.engine import Engine
    from language.model import NAtlasLLM

    engine = Engine(NAtlasLLM())
    hits = 0
    for r in rows:
        res = engine.step(normalise(r["utterance"], lang).text, lang, r["spec"], [], date.today())
        hits += res.action == "edit" and res.payload["edit"] == r["expected"]
    return {"edit_success": metrics.rate(hits, len(rows))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("kind", choices=["numbers", "asr", "spec", "edits"])
    ap.add_argument("lang", choices=["ha", "ig", "yo", "en"])
    ap.add_argument("--data")
    args = ap.parse_args()

    path = args.data or HERE / "data" / f"{args.kind}_{args.lang}.jsonl"
    rows = read(path)
    if args.kind == "numbers":
        out = run_numbers(rows, args.lang)
    elif args.kind == "asr":
        terms_file = HERE / "data" / "business_terms.txt"
        terms = terms_file.read_text(encoding="utf-8").split() if terms_file.exists() else []
        out = run_asr(rows, args.lang, terms)
    elif args.kind == "spec":
        out = run_spec(rows, args.lang)
    else:
        out = run_edits(rows, args.lang)

    out.update(kind=args.kind, lang=args.lang, data=str(path))
    results = HERE / "results"
    results.mkdir(exist_ok=True)
    (results / f"{args.kind}_{args.lang}.json").write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
