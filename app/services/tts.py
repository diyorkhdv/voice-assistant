"""Text-to-Speech (the "Mouth").

Production path: OpenAI TTS (`tts-1`) returning mp3 bytes.
Mock path: returns a tiny valid silent MP3 frame so the JSON contract
(audio as Base64) is identical in both modes and the UI can still "play" it.
"""
from __future__ import annotations

import base64

from app.config import get_settings
from app.services.openai_client import get_async_client

# A minimal, valid silent MP3 frame (used only in mock mode).
_SILENT_MP3 = base64.b64decode(
    "SUQzBAAAAAAAI1RTU0UAAAAPAAADTGF2ZjU4Ljc2LjEwMAAAAAAAAAAAAAAA//tQxAADB8AhSm"
    "xhIIEVCSiprDCQBTJ0OEElQ1RTU0UAAAAPAAADTGF2ZjU4Ljc2LjEwMA=="
)


class TextToSpeech:
    def __init__(self) -> None:
        self.settings = get_settings()

    async def synthesize(self, text: str) -> bytes:
        if self.settings.use_mock:
            return _SILENT_MP3

        client = get_async_client()
        resp = await client.audio.speech.create(
            model=self.settings.tts_model,
            voice=self.settings.tts_voice,
            input=text,
            response_format="mp3",
        )
        return resp.read()

    async def synthesize_b64(self, text: str) -> str:
        audio = await self.synthesize(text)
        return base64.b64encode(audio).decode("ascii")
