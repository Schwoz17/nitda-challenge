# [Project name]

Voice-first app builder for small traders in Hausa, Igbo, Yoruba and English, built on N-ATLAS for the National AI Innovation Challenge 2026 (Problem Statement 2: Voice-First Access).

A trader describes their business by voice. The system builds a small app (first pilot: a debt tracker), and the trader adds and changes entries by voice. Every amount is checked in code and read back to the trader before it is saved.

## How N-ATLAS is used
- Language model: `NCAIR1/N-ATLaS` (pinned in `models.lock.json`)
- Speech recognition: `NCAIR1/Hausa-ASR`, `NCAIR1/Igbo-ASR`, `NCAIR1/Yoruba-ASR`, `NCAIR1/NigerianAccentedEnglish`
- No other AI model is used. `python scripts/check_models.py` checks this.

## Pipeline
audio -> ASR -> normaliser (numbers, dates) -> N-ATLaS -> validator -> read-back -> save and log

## Run the tests
    pip install pytest
    python -m pytest
    python scripts/check_models.py

## Run the service (needs a GPU and access to the gated N-ATLaS model)
    pip install -r requirements.txt
    huggingface-cli login
    MAGANA_4BIT=1 uvicorn service:app --port 8000

Calls: `POST /session`, `POST /turn` (audio or text), `POST /tap`. See the technical documentation in `docs/`.

## Status
Working end to end on typed text in all four languages. Voice input through the official ASR models is being tested. Per-language results from native-speaker testing will be added to `docs/`.

## Team
Muiz Adeyemi: language and voice pipeline, evaluation, documentation
AbdulWahab Yusuf: app generator, web app, deployment