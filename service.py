import os
import tempfile
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from config import LANGS
from pipeline import Pipeline

@asynccontextmanager
async def lifespan(_):
    if os.environ.get("MAGANA_PRELOAD") == "1":
        from asr.client import preload
        pipeline()
        preload()
    yield


app = FastAPI(title="Magana pipeline", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("MAGANA_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)
_pipeline = None


def pipeline():
    global _pipeline
    if _pipeline is None:
        from language.model import NAtlasLLM
        _pipeline = Pipeline(NAtlasLLM(quantize=os.environ.get("MAGANA_4BIT") == "1"),
                             seed_every=int(os.environ.get("MAGANA_SEED_EVERY", "0")))
    return _pipeline


@app.get("/health")
def health():
    from asr.client import loaded
    return {"ok": True, "model_ready": _pipeline is not None, "asr_ready": loaded()}


@app.post("/session")
def new_session():
    return {"session": uuid.uuid4().hex[:12]}


@app.post("/turn")
async def turn(session: str = Form(...), lang: str = Form(...),
               audio: UploadFile | None = File(None), text: str | None = Form(None)):
    if lang not in LANGS:
        raise HTTPException(400, "unsupported language")
    if audio is None and text is None:
        raise HTTPException(400, "send audio or text")
    path = None
    if audio is not None:
        suffix = Path(audio.filename or "clip.wav").suffix or ".wav"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(await audio.read())
            path = tmp.name
    try:
        return pipeline().turn(session, lang, audio=path, text=text)
    finally:
        if path:
            os.unlink(path)


@app.post("/tap")
def tap(session: str = Form(...), accepted: bool = Form(...)):
    if session not in pipeline().sessions:
        raise HTTPException(404, "unknown session")
    return pipeline().confirm_tap(session, accepted)