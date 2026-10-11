import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LANGS = ("ha", "ig", "yo", "en")
LANG_NAMES = {"ha": "Hausa", "ig": "Igbo", "yo": "Yoruba", "en": "English"}

LOG_DIR = Path(os.environ.get("MAGANA_LOG_DIR", ROOT / "logs"))
DB_PATH = Path(os.environ.get("MAGANA_DB", ROOT / "magana.db"))
PROMPT_TOKEN_BUDGET = 6000


def load_lock():
    with open(ROOT / "models.lock.json", encoding="utf-8") as f:
        return json.load(f)
