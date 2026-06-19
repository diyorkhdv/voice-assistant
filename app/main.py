"""FastAPI application exposing both interview tasks.

  POST /api/v1/voice-intent       -> V1 Voice Intent Agent
  POST /api/v2/banking-assistant  -> V2 Personal Banking Voice Assistant
  GET  /                          -> mini web UI
  GET  /health                    -> liveness + mode

All AI calls are async so the event loop stays free under concurrency, which is
what keeps voice latency low when many requests arrive at once.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import logging
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from openai import OpenAIError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.database import get_session
from app.db.repository import BankingRepository
from app.db.seed import seed
from app.schemas import (
    BankingIntent,
    BankingResponse,
    Intent,
    VoiceIntentResponse,
)
from app.services import LanguageModel, SpeechToText, TextToSpeech

settings = get_settings()
STATIC_DIR = Path(__file__).parent / "static"

log = logging.getLogger("uvicorn")

# Demo "today" anchor, aligned with the seeded data, so "yesterday" resolves
# deterministically. In production this would be `dt.date.today()`.
REFERENCE_TODAY = dt.date(2026, 6, 19)

ALLOWED_TYPES = {"audio/wav", "audio/x-wav", "audio/wave", "audio/mpeg", "audio/mp3"}
ALLOWED_EXT = {".wav", ".mp3", ".mpeg", ".m4a", ".webm", ".ogg"}

# Live STT model status, surfaced to the UI via GET /api/status so the page can
# show a loading indicator while the offline Whisper model downloads/loads.
#   state: "mock" | "loading" | "ready" | "error" | "idle"
STT_STATUS: dict = {"state": "idle", "model": settings.whisper_model, "detail": "", "elapsed_s": 0.0}


async def _load_stt_model() -> None:
    """Load the Whisper model in the background (off the event loop) so the
    server can serve the UI immediately and report progress via /api/status."""
    # Lift the HF anonymous download rate limit if a token is configured.
    if settings.hf_token:
        os.environ.setdefault("HF_TOKEN", settings.hf_token)
    started = time.perf_counter()
    STT_STATUS.update(state="loading", detail="Downloading / loading model…", _started=started)
    log.info("Loading offline Whisper model '%s' (first run downloads it)…", settings.whisper_model)
    try:
        await asyncio.to_thread(stt._get_model)
        STT_STATUS.update(state="ready", detail="", elapsed_s=round(time.perf_counter() - started, 1))
        log.info("Whisper model ready (%.1fs).", STT_STATUS["elapsed_s"])
    except Exception as exc:  # never crash startup
        STT_STATUS.update(state="error", detail=str(exc))
        log.warning("Whisper load failed (%s). Falls back to stub per request.", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    seed()  # ensure DB exists and demo data is present

    if settings.stt_use_mock:
        STT_STATUS["state"] = "mock"
    elif settings.preload_stt:
        # Non-blocking: kick off the load and let the UI poll /api/status.
        asyncio.create_task(_load_stt_model())
    else:
        STT_STATUS["state"] = "idle"  # will lazy-load on first request
    yield


app = FastAPI(
    title=settings.app_title,
    version="1.0.0",
    description="Voice-to-Intent (V1) and Voice-to-Data banking assistant (V2).",
    lifespan=lifespan,
)

@app.exception_handler(OpenAIError)
async def _openai_error(request: Request, exc: OpenAIError) -> JSONResponse:
    """Turn provider failures (bad key, no credit, rate limit) into a clean,
    readable 502 instead of an opaque 500. STT is local, so this only affects
    the LLM/TTS steps — the offline transcription still works."""
    log.warning("OpenAI provider error: %s", exc)
    return JSONResponse(
        status_code=502,
        content={"detail": f"OpenAI (LLM/TTS) call failed: {exc}. "
                           f"Check OPENAI_API_KEY and billing/credit, or set MOCK_MODE=true."},
    )


# Stateless singletons.
stt = SpeechToText()
llm = LanguageModel()
tts = TextToSpeech()


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
async def _read_audio(file: UploadFile) -> bytes:
    ext = Path(file.filename or "").suffix.lower()
    if file.content_type not in ALLOWED_TYPES and ext not in ALLOWED_EXT:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported audio type '{file.content_type or ext}'. Use .wav or .mp3.",
        )
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty audio file.")
    if len(data) > settings.max_audio_mb * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"Audio exceeds {settings.max_audio_mb} MB.")
    return data


def _wants_yesterday(text: str) -> bool:
    return "yesterday" in (text or "").lower()


# --------------------------------------------------------------------------- #
# Health / UI
# --------------------------------------------------------------------------- #
@app.get("/health", tags=["meta"])
async def health() -> dict:
    return {"status": "ok", "mock_mode": settings.use_mock, "version": app.version}


# Approx on-disk download size (MB) per faster-whisper model, for a progress %.
_WHISPER_MB = {"tiny": 75, "base": 145, "small": 488, "medium": 1530, "large-v3": 3090}


def _stt_download_progress() -> tuple[float, float]:
    """(downloaded_mb, total_mb) by measuring the model's HF cache blobs dir.
    HuggingFace exposes no progress callback, so we read bytes-on-disk (partial
    `.incomplete` files included) against the model's known size."""
    total_mb = float(_WHISPER_MB.get(settings.whisper_model, 145))
    try:
        from huggingface_hub.constants import HF_HUB_CACHE
        blobs = Path(HF_HUB_CACHE) / f"models--Systran--faster-whisper-{settings.whisper_model}" / "blobs"
        if not blobs.exists():
            return 0.0, total_mb
        got = sum(f.stat().st_size for f in blobs.iterdir() if f.is_file())
        return round(got / 1e6, 1), total_mb
    except Exception:
        return 0.0, total_mb


@app.get("/api/status", tags=["meta"])
async def status() -> dict:
    """STT model load state (+ live elapsed time, + download progress) and the
    LLM/TTS mock flag. The UI polls this to show a Whisper loading indicator
    and gate the buttons."""
    s = dict(STT_STATUS)
    if s["state"] == "loading":
        if s.get("_started"):
            s["elapsed_s"] = round(time.perf_counter() - s["_started"], 1)
        got, total = _stt_download_progress()
        s["downloaded_mb"], s["total_mb"] = got, total
    s.pop("_started", None)
    return {"stt": s, "mock_mode": settings.use_mock}


if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


# --------------------------------------------------------------------------- #
# V1 — Voice Intent Agent
# --------------------------------------------------------------------------- #
@app.post("/api/v1/voice-intent", response_model=VoiceIntentResponse, tags=["v1"])
async def voice_intent(file: UploadFile = File(...)) -> VoiceIntentResponse:
    start = time.perf_counter()
    audio = await _read_audio(file)

    transcript = await stt.transcribe(audio, file.filename or "audio.wav")
    intent: Intent = await llm.classify_intent(transcript)

    reply_text = f"I have categorized your request as {intent.value}."
    audio_b64 = await tts.synthesize_b64(reply_text)

    return VoiceIntentResponse(
        transcript=transcript,
        intent=intent,
        reply_text=reply_text,
        audio_base64=audio_b64,
        latency_ms=round((time.perf_counter() - start) * 1000, 1),
        mock=settings.use_mock,
    )


# --------------------------------------------------------------------------- #
# V2 — Personal Banking Voice Assistant
# --------------------------------------------------------------------------- #
@app.post("/api/v2/banking-assistant", response_model=BankingResponse, tags=["v2"])
async def banking_assistant(
    user_id: int = Form(..., ge=1, description="Authenticated user id."),
    file: UploadFile = File(...),
    db: Session = Depends(get_session),
) -> BankingResponse:
    start = time.perf_counter()
    audio = await _read_audio(file)

    transcript = await stt.transcribe(audio, file.filename or "audio.wav")
    intent: BankingIntent = await llm.classify_banking_intent(transcript)

    repo = BankingRepository(db)
    if intent is BankingIntent.BALANCE:
        data = repo.get_balance(user_id)
    elif intent is BankingIntent.TRANSACTIONS:
        if _wants_yesterday(transcript):
            yday = REFERENCE_TODAY - dt.timedelta(days=1)
            data = repo.get_transactions(user_id, since=yday, until=yday)
        else:
            data = repo.get_transactions(user_id)
    else:
        data = {"kind": "unknown"}

    # The synthesis step is grounded strictly in `data`; numbers can't be invented.
    answer_text = await llm.synthesize_answer(transcript, data)
    audio_b64 = await tts.synthesize_b64(answer_text)

    return BankingResponse(
        transcript=transcript,
        intent=intent,
        answer_text=answer_text,
        data=data,
        audio_base64=audio_b64,
        latency_ms=round((time.perf_counter() - start) * 1000, 1),
        mock=settings.use_mock,
    )
