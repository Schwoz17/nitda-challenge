import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_only_natlas_models_configured():
    r = subprocess.run([sys.executable, "scripts/check_models.py"], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout
