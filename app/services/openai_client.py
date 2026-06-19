"""Shared async OpenAI client factory.

A single AsyncOpenAI instance is reused across services so connections are
pooled. Returns ``None`` in mock mode so callers can branch cheaply.
"""
from __future__ import annotations

from functools import lru_cache

from openai import AsyncOpenAI

from app.config import get_settings


@lru_cache
def get_async_client() -> AsyncOpenAI | None:
    settings = get_settings()
    if settings.use_mock:
        return None
    return AsyncOpenAI(api_key=settings.openai_api_key)
