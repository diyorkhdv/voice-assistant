"""AI service layer: Speech-to-Text, LLM reasoning, Text-to-Speech.

Each service exposes an async interface and transparently falls back to a
deterministic MOCK implementation when no OpenAI key is configured, so the
whole pipeline is runnable and testable offline.
"""
from .stt import SpeechToText
from .llm import LanguageModel
from .tts import TextToSpeech

__all__ = ["SpeechToText", "LanguageModel", "TextToSpeech"]
