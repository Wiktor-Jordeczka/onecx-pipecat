"""Speech adapters: STT (text-out) and TTS (text-in, audio-out).

Both adapters are *streaming*: ``stream`` is an async generator that yields
interim results as they arrive. STT yields ``(text, is_final)`` pairs so partial
transcripts can be streamed to the client while only the final one is persisted;
TTS yields audio chunks so the assistant's speech can be played incrementally.
The one-shot ``transcribe``/``synthesize`` helpers are thin wrappers over
``stream`` and keep deterministic callers (and the in-memory doubles) simple.

The AWS adapters drive Pipecat's AWS services over a pinned language's profile.
They are deployment-only: Pipecat's AWS services require the ``pipecat-ai[aws]``
extra and AWS credentials at runtime, so the imports and service construction
are deferred into ``stream`` — a container (and the ``/healthz`` adapter summary)
never touches AWS until a voice turn actually runs.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Protocol
from uuid import uuid4

from onecx_pipecat.config import AwsSpeechProfile, SpeechSettings

# One-shot transcription/synthesis is bounded well below a real voice turn; it
# guards against a stuck AWS stream wedging a turn open-ended.
_AWS_TIMEOUT_SECONDS = 30.0


class UnsupportedLanguageError(Exception):
    """Raised when a pinned language has no AWS speech profile configured."""


def resolve_profile(settings: SpeechSettings, language_code: str) -> AwsSpeechProfile:
    """Map a pinned language to its AWS Transcribe/Polly profiles.

    An empty code falls back to the configured default language. A language
    that is not a key in ``aws_profiles`` is unsupported and raises
    ``UnsupportedLanguageError`` rather than guessing a profile.
    """
    code = language_code or settings.default_language
    profile = settings.aws_profiles.get(code)
    if profile is None:
        raise UnsupportedLanguageError(
            f"no AWS speech profile for language {code!r}; "
            f"configured: {sorted(settings.aws_profiles)}"
        )
    return profile


class SttAdapter(Protocol):
    async def transcribe(self, audio_bytes: bytes) -> str: ...

    def stream(self, audio_bytes: bytes) -> AsyncIterator[tuple[str, bool]]: ...


class TtsAdapter(Protocol):
    async def synthesize(self, text: str) -> bytes: ...

    def stream(self, text: str) -> AsyncIterator[bytes]: ...


class InMemorySttAdapter:
    """Deterministic echo: the transcript is a fixed string for any input."""

    def __init__(self, settings: SpeechSettings | None = None) -> None:
        self._settings = settings or SpeechSettings()
        self._fallback = "in-memory transcript"

    async def transcribe(self, audio_bytes: bytes) -> str:
        if not audio_bytes:
            return ""
        return self._fallback

    async def stream(self, audio_bytes: bytes) -> AsyncIterator[tuple[str, bool]]:
        # The in-memory adapter has no partials; it yields a single final
        # transcript. Empty input yields nothing (noise-only stays ephemeral).
        if not audio_bytes:
            return
        yield self._fallback, True


class InMemoryTtsAdapter:
    """Deterministic bytes: length tracks the text; no real synthesis."""

    def __init__(self, settings: SpeechSettings | None = None) -> None:
        self._settings = settings or SpeechSettings()

    async def synthesize(self, text: str) -> bytes:
        if not text:
            return b""
        return text.encode("utf-8")

    async def stream(self, text: str) -> AsyncIterator[bytes]:
        if not text:
            return
        yield text.encode("utf-8")


class AwsSttAdapter:
    """AWS Transcribe STT for one pinned language.

    Drives Pipecat's ``AWSTranscribeSTTService`` through a one-shot direct-mode
    pipeline and surfaces the service's ``TranscriptionFrame``s (partial and
    final). The service is imported and constructed lazily in ``stream``.
    """

    def __init__(self, settings: SpeechSettings, profile: AwsSpeechProfile) -> None:
        self._settings = settings
        self._profile = profile

    def __repr__(self) -> str:  # pragma: no cover - diagnostic
        return f"AwsSttAdapter(language={self._profile.transcribe_language!r})"

    async def transcribe(self, audio_bytes: bytes) -> str:
        """Convenience: the full final transcript for a chunk of audio."""
        final = ""
        async for text, is_final in self.stream(audio_bytes):
            if is_final:
                final = text
        return final

    async def stream(self, audio_bytes: bytes) -> AsyncIterator[tuple[str, bool]]:
        if not audio_bytes:
            return
        from pipecat.clocks.system_clock import SystemClock
        from pipecat.frames.frames import AudioRawFrame, EndFrame, TranscriptionFrame
        from pipecat.pipeline.pipeline import Pipeline
        from pipecat.processors.frame_processor import (
            FrameDirection,
            FrameProcessor,
            FrameProcessorSetup,
        )
        from pipecat.services.aws.stt import AWSTranscribeSTTService, AWSTranscribeSTTSettings
        from pipecat.utils.asyncio.task_manager import TaskManager

        done = asyncio.Event()
        transcriptions: list[TranscriptionFrame] = []

        class _Collector(FrameProcessor):
            def __init__(self) -> None:
                super().__init__(enable_direct_mode=True)

            async def process_frame(self, frame, _direction):
                if isinstance(frame, TranscriptionFrame):
                    transcriptions.append(frame)
                    if frame.finalized:
                        done.set()
                elif isinstance(frame, EndFrame):
                    done.set()
                await self.push_frame(frame, FrameDirection.DOWNSTREAM)

        service = AWSTranscribeSTTService(
            region=self._settings.region,
            sample_rate=self._settings.sample_rate_hz,
            settings=AWSTranscribeSTTSettings(language=self._profile.transcribe_language),
        )
        pipeline = Pipeline([service, _Collector()])
        setup = FrameProcessorSetup(
            clock=SystemClock(), task_manager=TaskManager(), pipeline_worker=None
        )
        await pipeline.setup(setup)
        try:
            await pipeline.queue_frame(AudioRawFrame(audio_bytes, self._settings.sample_rate_hz, 1))
            await pipeline.queue_frame(EndFrame())
            await asyncio.wait_for(done.wait(), timeout=_AWS_TIMEOUT_SECONDS)
        finally:
            try:
                await asyncio.wait_for(pipeline.cleanup(), timeout=3.0)
            except Exception:  # noqa: BLE001 - cleanup must never mask the result
                pass
        for frame in transcriptions:
            yield frame.text, bool(frame.finalized)


class AwsTtsAdapter:
    """Amazon Polly TTS for one pinned language.

    Calls Pipecat's ``AWSPollyTTSService.run_tts`` — its documented synthesis
    generator — and yields the ``TTSAudioRawFrame`` audio chunks it produces.
    ``run_tts`` is a self-terminating async generator, so a single call drives
    one utterance to completion with no end-frame bookkeeping. The Polly module
    imports ``aiobotocore`` at load, so the import and the service's ``setup``
    (which provisions its resampler) happen in ``stream``.
    """

    def __init__(self, settings: SpeechSettings, profile: AwsSpeechProfile) -> None:
        self._settings = settings
        self._profile = profile

    def __repr__(self) -> str:  # pragma: no cover - diagnostic
        return f"AwsTtsAdapter(voice={self._profile.polly_voice!r})"

    async def synthesize(self, text: str) -> bytes:
        """Convenience: the full audio for a piece of text."""
        return b"".join([chunk async for chunk in self.stream(text)])

    async def stream(self, text: str) -> AsyncIterator[bytes]:
        if not text:
            return
        from pipecat.clocks.system_clock import SystemClock
        from pipecat.frames.frames import TTSAudioRawFrame
        from pipecat.pipeline.pipeline import Pipeline
        from pipecat.processors.frame_processor import FrameProcessorSetup
        from pipecat.services.aws.tts import AWSPollyTTSService
        from pipecat.utils.asyncio.task_manager import TaskManager

        service = AWSPollyTTSService(
            region=self._settings.region,
            sample_rate=self._settings.sample_rate_hz,
            settings=AWSPollyTTSService.Settings(
                voice=self._profile.polly_voice,
                language=self._profile.transcribe_language,
            ),
        )
        # The service must be set up (which provisions its resampler) before
        # ``run_tts``; a one-processor pipeline is a convenient way to run
        # ``setup``/``cleanup`` against the real ``FrameProcessor`` lifecycle.
        pipeline = Pipeline([service])
        setup = FrameProcessorSetup(
            clock=SystemClock(), task_manager=TaskManager(), pipeline_worker=None
        )
        await pipeline.setup(setup)
        context_id = f"onecx-{uuid4().hex}"
        try:
            async for frame in service.run_tts(text, context_id):
                if isinstance(frame, TTSAudioRawFrame):
                    yield frame.audio
        finally:
            try:
                await asyncio.wait_for(pipeline.cleanup(), timeout=3.0)
            except Exception:  # noqa: BLE001 - cleanup must never mask the result
                pass
