# Reviewer Notes

Quick, dense overview for evaluation. Full setup is in [README.md](README.md).

## What this is

One **FastAPI** service implementing both interview tasks:

- **V1 — Voice Intent Agent:** audio → transcript → intent (`Query` / `Action` / `SmallTalk`) → spoken confirmation.
- **V2 — Banking Voice Assistant:** audio + `user_id` → transcript → DB lookup → natural spoken answer grounded in real account data.

Pipeline: **offline Whisper (local STT) → GPT (intent / synthesis) → OpenAI TTS**, fully async.

## Stack

| Layer | Choice | Why |
|---|---|---|
| API | FastAPI + Uvicorn | async, auto OpenAPI/Swagger |
| STT | `faster-whisper` (CTranslate2), **local/offline** | no per-call cost, no audio leaves the host (PII-safe), no key needed |
| LLM | OpenAI `gpt-4o-mini` (JSON mode, `temp=0`) | cheap, fast, strict parseable output |
| TTS | OpenAI `tts-1` | natural speech, mp3 |
| DB | SQLAlchemy ORM (SQLite default, Postgres-ready) | parameterized, safe |
| Validation | Pydantic v2 | typed request/response contracts |
| Tests | pytest + httpx TestClient | 23 tests, fully offline |
| Packaging | Docker + docker-compose | one-command run |

## Functionality

- Two endpoints (`/api/v1/voice-intent`, `/api/v2/banking-assistant`) + mini web UI at `/` + Swagger at `/docs` + `/health`.
- Record-from-mic or file upload; returns transcript, intent, text answer, and reply audio (Base64) + `latency_ms`.
- **Mock fallback:** runs with no OpenAI key and (via `MOCK_MODE=true`) with no model download — so it boots and tests pass anywhere.
- Whisper pinned to English (`WHISPER_LANGUAGE=en`); model pre-loaded at startup.

## How the evaluation criteria are addressed

- **Latency:** all I/O async; one pooled `AsyncOpenAI` client; blocking Whisper decode offloaded via `asyncio.to_thread`; `latency_ms` returned per request.
- **Logic & prompting:** Chat Completions JSON mode, `temperature=0`, closed label set, explicit defaults for empty/garbled input, safe fallback on off-contract output.
- **Architecture:** clean transport ↔ services ↔ data split; providers behind a thin abstraction with mocks; swappable without touching endpoints.
- **Tool selection:** local Whisper (cost/privacy) + small GPT + OpenAI TTS + FastAPI + SQLAlchemy.
- **Accuracy (V2):** answers use only DB numbers; synthesis prompt constrained to provided JSON; mock path templates from the same data.
- **SQL safety (V2):** **the LLM never writes SQL** — it only picks an intent label; data is fetched with parameterized ORM queries, `user_id` integer-bound. Test fires `DROP TABLE` and verifies the table survives.
- **Data handling:** empty transactions and missing accounts return clear messages, never a crash or fabricated number.

## Database (seeded automatically on startup)

Schema: `accounts(user_id, balance, currency)`, `transactions(id, user_id, amount, merchant, date)`.

| user_id | balance | transactions |
|---|---|---|
| 1 | 1250 UZS | Korzinka 50000 (yesterday), Yandex Go 12000 (today), Evos 8500 |
| 2 | 500 USD | Starbucks 42.50, Uber 120 |
| 3 | 0 UZS | **none** — no-data edge case |

Unknown `user_id` (e.g. 99) → "account not found" message.

## Key files / scripts

| Path | Purpose |
|---|---|
| `app/main.py` | FastAPI app, both endpoints, startup warm-up, OpenAI-error handler |
| `app/config.py` | env-driven settings + mock logic |
| `app/services/stt.py` | offline Whisper transcription (+ mock) |
| `app/services/llm.py` | intent classification + grounded synthesis (+ mock); **SQL-safety design notes** |
| `app/services/tts.py` | OpenAI TTS (+ mock) |
| `app/db/models.py` · `repository.py` · `database.py` · `seed.py` | ORM models, parameterized queries, engine, demo seed |
| `app/static/index.html` | single-page UI |
| `tests/` | `test_intent.py`, `test_banking.py`, `test_api.py` (23 tests) |
| `examples/requests.sh` | ready-made curl calls for every case |
| `python -m app.db.seed` | (re)seed the database manually |
| `pytest -v` | run the suite (offline, mock mode) |

## Run in 30 seconds

```bash
# fully offline, no key, no download:
MOCK_MODE=true uvicorn app.main:app --reload      # → http://localhost:8000
# real pipeline: add OPENAI_API_KEY to .env, then `uvicorn app.main:app --reload`
# tests:
pytest -v
```
