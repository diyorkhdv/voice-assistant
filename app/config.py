"""Application configuration.

Centralised settings loaded from environment variables (12-factor style).

STT runs a LOCAL, offline Whisper model (faster-whisper) — no API key needed.
The LLM (intent + synthesis) and TTS use OpenAI; if no OPENAI_API_KEY is present
those two fall back to deterministic stubs so the service still boots and tests
pass. Set MOCK_MODE=true to stub everything (used by CI to skip the model load).
"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- OpenAI (LLM + TTS only; STT is local) ---
    openai_api_key: str | None = None
    llm_model: str = "gpt-4o-mini"
    tts_model: str = "tts-1"
    tts_voice: str = "alloy"

    # --- Offline Whisper STT (faster-whisper / CTranslate2) ---
    # Model is downloaded once from HuggingFace, then runs fully offline.
    whisper_model: str = "base"          # tiny | base | small | medium | large-v3
    whisper_device: str = "cpu"          # cpu | cuda
    whisper_compute_type: str = "int8"   # int8 (cpu) | float16 (gpu)
    whisper_beam_size: int = 1           # 1 = greedy = fastest
    # Force a transcription language ("en"). Empty string = auto-detect (multilingual).
    whisper_language: str = "en"
    # Load the model during startup (warm-up) instead of on the first request,
    # so the server only goes live once the model is downloaded & ready.
    preload_stt: bool = True
    # Optional free HuggingFace token — lifts the anonymous download rate limit
    # (anonymous pulls can be throttled to a crawl). Get one at hf.co/settings/tokens.
    hf_token: str | None = None

    # --- Behaviour ---
    # Stub ALL providers (STT/LLM/TTS). Used by tests/CI to avoid any download
    # or network call. Real STT still works offline when this is False.
    mock_mode: bool = False

    # --- Database ---
    database_url: str = "sqlite:///./banking.db"

    # --- App ---
    app_title: str = "Voice Intent & Banking Assistant"
    max_audio_mb: int = 25

    @property
    def stt_use_mock(self) -> bool:
        """STT is local and needs no key, so only stub it in explicit mock mode."""
        return self.mock_mode

    @property
    def use_mock(self) -> bool:
        """LLM/TTS stub: explicit mock mode OR no OpenAI key available."""
        return self.mock_mode or not self.openai_api_key


@lru_cache
def get_settings() -> Settings:
    return Settings()
