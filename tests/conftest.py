"""Shared test fixtures.

Forces MOCK mode and an isolated temp SQLite DB so the whole suite runs offline
with zero external dependencies.
"""
import os
import tempfile

import pytest

# Must be set BEFORE app modules import settings.
os.environ["MOCK_MODE"] = "true"
os.environ["OPENAI_API_KEY"] = ""
_tmp_db = os.path.join(tempfile.gettempdir(), "test_banking.db")
if os.path.exists(_tmp_db):
    os.remove(_tmp_db)
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp_db}"


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:  # triggers lifespan -> seed()
        yield c


def make_audio(transcript: str, ext: str = "wav"):
    """Build a multipart file whose name carries the demo transcript (mock STT)."""
    safe = transcript.replace(" ", "_").replace("?", "")
    name = f"clip__transcript__{safe}.{ext}"
    return {"file": (name, b"RIFF....fake", "audio/wav")}
