# Farmer Assistant

An AI crop advisor on WhatsApp/Telegram. Farmers send a question, voice note or
photo of a sick plant and get advice grounded only in vetted agricultural
documents, in their own language, with an expert fallback when unsure.

Phase 1 MVP: one crop, one region, one language. See [CLAUDE.md](CLAUDE.md) for
scope, the safety rules and architecture.

## Quick start

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env    # add ANTHROPIC_API_KEY and the Phase 0 choices
```

1. Put vetted documents in `data/sources/` and list them in `data/sources/sources.json`
   (see `data/sources/README.md`).
2. `python scripts/ingest.py` (the first run downloads an ~80 MB embedding model).
3. Try it: `python scripts/ask.py "leaves have brown spots with grey centre"`
4. Telegram test bot: set `TELEGRAM_BOT_TOKEN`, then `python scripts/telegram_polling.py`.

## How an answer is made safe

1. Photo → Claude vision **diagnoses only** (no treatment).
2. Question/diagnosis → English search query → top chunks from the vetted sources.
3. Claude answers from those chunks only and returns verbatim quotes for every dose
   and safety step, plus a confidence level.
4. `app/safety/guard.py` checks the quotes are really in the sources and every number
   in the answer appears in them. Anything unverifiable, low-confidence or unsourced
   becomes "please contact an expert".
5. The farmer sees the answer, the exact source quotes, and the source names.

## Tests

```bash
pytest
ruff check . && black --check .
```
