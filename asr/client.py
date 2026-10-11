from dataclasses import dataclass
from functools import lru_cache

from config import LANGS, load_lock


class ASRError(Exception):
    pass


@dataclass
class Transcript:
    text: str
    lang: str
    model: str
    revision: str
    confidence: float | None = None


@lru_cache(maxsize=None)
def _load(model, revision):
    import torch
    from transformers import pipeline

    device = 0 if torch.cuda.is_available() else -1
    return pipeline(
        "automatic-speech-recognition",
        model=model,
        revision=revision or None,
        device=device,
        chunk_length_s=30,
    )


def transcribe(audio_path, lang):
    if lang not in LANGS:
        raise ASRError(f"unsupported language: {lang}")
    entry = load_lock()["asr"].get(lang) or {}
    model = entry.get("model")
    if not model:
        raise ASRError(f"no ASR model set for '{lang}' in models.lock.json")
    revision = entry.get("revision", "")
    try:
        out = _load(model, revision)(str(audio_path))
    except Exception as exc:
        raise ASRError(str(exc)) from exc
    text = (out.get("text") or "").strip()
    if not text:
        raise ASRError("empty transcript")
    return Transcript(text=text, lang=lang, model=model, revision=revision)
