"""Pydantic request/response models shared across endpoints."""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


# ----------------------------- V1: Voice Intent ----------------------------- #
class Intent(str, Enum):
    QUERY = "Query"
    ACTION = "Action"
    SMALLTALK = "SmallTalk"


class VoiceIntentResponse(BaseModel):
    transcript: str = Field(..., description="Text transcribed from the audio.")
    intent: Intent = Field(..., description="Classified intent.")
    reply_text: str = Field(..., description="Confirmation sentence spoken back.")
    audio_base64: str = Field(..., description="Reply audio (mp3) as Base64.")
    audio_format: str = "mp3"
    latency_ms: float = Field(..., description="Server-side processing time.")
    mock: bool = Field(..., description="True if AI providers were mocked.")


# --------------------------- V2: Banking Assistant -------------------------- #
class BankingIntent(str, Enum):
    BALANCE = "balance"
    TRANSACTIONS = "transactions"
    UNKNOWN = "unknown"


class BankingResponse(BaseModel):
    transcript: str
    intent: BankingIntent
    answer_text: str = Field(..., description="Natural-language answer grounded in DB data.")
    data: dict = Field(default_factory=dict, description="Raw data used to build the answer.")
    audio_base64: str
    audio_format: str = "mp3"
    latency_ms: float
    mock: bool


class ErrorResponse(BaseModel):
    detail: str
