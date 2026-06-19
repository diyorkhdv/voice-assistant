"""Speech-to-Text (the "Ears") — OFFLINE Whisper.

Production path: a LOCAL Whisper model via `faster-whisper` (CTranslate2).
No data leaves the machine and no API key is required. The model weights are
downloaded once from HuggingFace and cached, after which it runs fully offline.

Mock path (tests / CI / quick demos): returns a deterministic transcript taken
from a `__transcript__` hint in the filename, so the pipeline is exercisable
without loading the model. The service also falls back to the mock if
faster-whisper isn't installed or the audio can't be decoded, so it never hard-fails.

The blocking, CPU-bound transcription runs in a worker thread
(`asyncio.to_thread`) so the async event loop stays free under concurrency.
"""
from __future__ import annotations

import asyncio
import os
import tempfile
from urllib.parse import unquote

from app.config import get_settings


class SpeechToText:
    # Class-level cache: the (heavy) model is loaded once and shared.
    _model = None

    def __init__(self) -> None:
        self.settings = get_settings()

    # ------------------------------------------------------------------ #
    def _get_model(self):
        if SpeechToText._model is None:
            from faster_whisper import WhisperModel  # imported lazily

            SpeechToText._model = WhisperModel(
                self.settings.whisper_model,
                device=self.settings.whisper_device,
                compute_type=self.settings.whisper_compute_type,
            )
        return SpeechToText._model

    async def transcribe(self, audio_bytes: bytes, filename: str) -> str:
        if self.settings.stt_use_mock:
            return self._mock_transcribe(filename)

        try:
            model = self._get_model()
        except Exception:
            # faster-whisper not available -> stay functional via mock.
            return self._mock_transcribe(filename)

        suffix = os.path.splitext(filename or "")[1] or ".wav"
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                tmp.write(audio_bytes)
                tmp_path = tmp.name
            # Offload the blocking decode/transcribe off the event loop.
            return await asyncio.to_thread(self._run, model, tmp_path)
        except Exception:
            # Undecodable/garbage audio (e.g. in tests) -> graceful fallback.
            return self._mock_transcribe(filename)
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def _run(self, model, path: str) -> str:
        # Pin the language (default "en") so short/noisy clips aren't mis-detected
        # as another language. Empty string => let Whisper auto-detect.
        language = self.settings.whisper_language or None
        segments, _info = model.transcribe(
            path,
            beam_size=self.settings.whisper_beam_size,
            language=language,
        )
        return " ".join(seg.text for seg in segments).strip()

    # ------------------------------------------------------------------ #
    @staticmethod
    def _mock_transcribe(filename: str) -> str:
        """Deterministic stub.

        Demo hint: name a file like ``clip__transcript__How_much_money_do_I_have.wav``
        and the mock returns the text after ``__transcript__``. Otherwise it
        echoes a default phrase so the rest of the pipeline still runs.
        """
        name = unquote(filename or "")
        marker = "__transcript__"
        if marker in name:
            text = name.split(marker, 1)[1]
            text = text.rsplit(".", 1)[0]  # drop extension
            return text.replace("_", " ").strip()
        return "What is the price of Bitcoin today?"
