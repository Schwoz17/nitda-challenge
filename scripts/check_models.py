import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ALLOWED_PREFIX = "NCAIR1/"
OTHER_PROVIDERS = [
    "api.openai.com", "api.anthropic.com", "generativelanguage.googleapis.com",
    "api.groq.com", "api.cohere", "api.mistral.ai", "api.deepseek.com",
    "openai.com/v1", "azure.com/openai", "bedrock-runtime", "whisper-1",
]
SCAN_SUFFIXES = {".py", ".json", ".env", ".txt", ".yaml", ".yml", ".toml", ".cfg", ".ini"}
SKIP_DIRS = {".git", "__pycache__", "logs", ".venv", "venv", "node_modules", "results"}


def main():
    problems = []
    lock = json.loads((ROOT / "models.lock.json").read_text(encoding="utf-8"))
    entries = [("llm", lock["llm"])] + [(f"asr.{k}", v) for k, v in lock["asr"].items()]
    for name, e in entries:
        model = e.get("model", "")
        if model and not model.startswith(ALLOWED_PREFIX):
            problems.append(f"{name}: {model} is not an N-ATLAS model")
        if model and not re.fullmatch(r"[0-9a-f]{40}", e.get("revision", "")):
            print(f"warning: {name} revision is not pinned to a commit sha")

    for path in ROOT.rglob("*"):
        if path.is_dir() or path.suffix not in SCAN_SUFFIXES or SKIP_DIRS & set(path.parts):
            continue
        if path.resolve() == Path(__file__).resolve():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore").lower()
        for needle in OTHER_PROVIDERS:
            if needle in text:
                problems.append(f"{path.relative_to(ROOT)} mentions {needle}")

    if problems:
        print("\n".join(problems))
        sys.exit(1)
    print("ok: only N-ATLAS models configured")


if __name__ == "__main__":
    main()
