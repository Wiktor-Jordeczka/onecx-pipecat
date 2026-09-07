"""Speech adapters: STT (text-out) and TTS (text-in, audio-out)."""

from __future__ import annotations

from typing import Protocol

from onecx_pipecat.config import SpeechSettings


class SttAdapter(Protocol):
    async def transcribe(self, audio_bytes: bytes) -> str: ...


class TtsAdapter(Protocol):
    async def synthesize(self, text: str) -> bytes: ...


class InMemorySttAdapter:
    """Deterministic echo: the transcript is a fixed string for any input."""

    def __init__(self, settings: SpeechSettings | None = None) -> None:
        self._settings = settings or SpeechSettings()
        self._fallback = "in-memory transcript"

    async def transcribe(self, audio_bytes: bytes) -> str:
        if not audio_bytes:
            return ""
        return self._fallback


class InMemoryTtsAdapter:
    """Deterministic bytes: length tracks the text; no real synthesis."""

    def __init__(self, settings: SpeechSettings | None = None) -> None:
        self._settings = settings or SpeechSettings()

    async def synthesize(self, text: str) -> bytes:
        if not text:
            return b""
        return text.encode("utf-8")
