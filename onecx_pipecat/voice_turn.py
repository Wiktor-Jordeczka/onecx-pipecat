"""One durable voice turn, driven by a real Pipecat pipeline.

A :class:`VoiceTurn` binds a single user utterance to a Pipecat ``Pipeline`` of
two OneCX bridges. The STT bridge streams the adapter's partial and final
transcripts through the pipeline; the TTS bridge, on those frames, streams the
transcript to the client (partials are never persisted), persists the single
durable ``HUMAN`` entry for the *final* transcript, emits the assistant caption,
and streams the assistant audio incrementally. Natural completion — and barge-in,
delivered by broadcasting a Pipecat ``InterruptionFrame`` (via
:meth:`FrameProcessor.broadcast_interruption`, which is not deprecated) from the
STT bridge — finalize the assistant entry in a terminal state (``COMPLETED`` or
``INTERRUPTED``, or not written at all when nothing was emitted).

Events are emitted through a sink callable (``on_event``) rather than returned
as a batch: captions and audio stream incrementally and a later user utterance
can interrupt mid-playback while the transport stays responsive. The sink may be
a plain synchronous function (tests) or an ``await``-able one (the transport),
and :meth:`VoiceTurn.emit` awaits it so events are sent in order.
"""

from __future__ import annotations

import asyncio
import base64
from typing import Any

from pipecat.clocks.system_clock import SystemClock
from pipecat.frames.frames import (
    AudioRawFrame,
    EndFrame,
    InterruptionFrame,
    StartFrame,
    TranscriptionFrame,
)
from pipecat.pipeline.pipeline import Pipeline
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor, FrameProcessorSetup
from pipecat.utils.asyncio.task_manager import TaskManager

from onecx_pipecat.models import VoiceEntry, VoiceEntryKind, VoiceEntryStatus
from onecx_pipecat.protocol import (
    AssistantAudio,
    AssistantText,
    ErrorEvent,
    Event,
    Transcript,
    TurnComplete,
)

# Bounded so a wedged pipeline/stream cannot keep a turn (and its session) open.
_TURNTIME_TIMEOUT = 30.0


def _frame_setup() -> FrameProcessorSetup:
    # A real clock and task manager, but no worker: the OneCX bridges are driven
    # directly (direct mode), so nothing must enqueue frames to a background loop.
    return FrameProcessorSetup(
        clock=SystemClock(), task_manager=TaskManager(), pipeline_worker=None
    )


class VoiceTurn:
    """Drive one STT->reply->TTS turn to a terminal state, with barge-in."""

    def __init__(
        self,
        *,
        stt: Any,
        tts: Any,
        on_event: Any,
        persistence: Any,
        session_id: str = "",
        sample_rate_hz: int = 16000,
    ) -> None:
        self._stt = stt
        self._tts = tts
        self._on_event = on_event
        self._persistence = persistence
        self._session_id = session_id
        self._sample_rate_hz = sample_rate_hz

        self._pipeline: Pipeline | None = None
        self._stt_bridge: SttBridge | None = None
        self._tts_bridge: TtsBridge | None = None
        self._audio_task: asyncio.Task[None] | None = None
        self._terminal = asyncio.Event()
        self._emitted_caption: str = ""
        self._assistant_entry_id: str | None = None
        self._assistant_finalized = False
        self._interrupted = False

    # -- barge-in -----------------------------------------------------------

    async def barge_in(self) -> None:
        """Interrupt the in-flight turn, stopping the assistant output.

        No-op when there is no active pipeline. Uses the non-deprecated
        :meth:`broadcast_interruption` so the ``InterruptionFrame`` reaches the
        TTS bridge, which cancels its in-flight audio and finalizes as
        ``INTERRUPTED``.
        """
        if self._stt_bridge is not None:
            await self._stt_bridge.broadcast_interruption()

    # -- lifecycle ----------------------------------------------------------

    async def run(self, audio: bytes) -> None:
        """Run one turn to a terminal state, emitting events via the sink."""
        if self._pipeline is not None:
            raise RuntimeError("a turn is already running")

        self._stt_bridge = SttBridge(self)
        self._tts_bridge = TtsBridge(self)
        self._pipeline = Pipeline([self._stt_bridge, self._tts_bridge])
        await self._pipeline.setup(_frame_setup())
        await self._pipeline.queue_frame(StartFrame())

        # Queuing the audio drives the STT bridge, which streams the
        # transcription frames through to the TTS bridge (direct mode awaits the
        # chain). The assistant audio is then streamed by a background task.
        await self._pipeline.queue_frame(AudioRawFrame(audio, self._sample_rate_hz, 1))

        try:
            await asyncio.wait_for(self._terminal.wait(), timeout=_TURNTIME_TIMEOUT)
        finally:
            await self._settle_audio()

    async def release(self) -> None:
        """Cancel any in-flight work and clean up the pipeline (idempotent).

        Also signals the turn's terminal state so a blocked ``run`` can settle,
        then cancels the audio task and releases the pipeline's resources.
        """
        self._terminal.set()
        if self._audio_task is not None and not self._audio_task.done():
            self._audio_task.cancel()
        self._audio_task = None
        if self._pipeline is not None:
            pipeline, self._pipeline = self._pipeline, None
            try:
                await asyncio.wait_for(pipeline.cleanup(), timeout=3.0)
            except Exception:  # noqa: BLE001 - release must never raise
                pass

    async def _settle_audio(self) -> None:
        if self._audio_task is not None and not self._audio_task.done():
            try:
                await asyncio.wait_for(self._audio_task, timeout=_TURNTIME_TIMEOUT)
            except (TimeoutError, asyncio.CancelledError):
                pass

    # -- state and helpers used by the bridges ------------------------------

    async def emit(self, event: Event) -> None:
        """Emit a typed event through the sink (sync or async callable)."""
        result = self._on_event(event)
        if asyncio.iscoroutine(result):
            await result

    def set_emitted_caption(self, text: str) -> None:
        self._emitted_caption = text

    async def persist_human(self, transcript: str) -> str | None:
        """Persist the one durable HUMAN entry; None on persistence failure."""
        entry = VoiceEntry(kind=VoiceEntryKind.HUMAN, text=transcript)
        try:
            return await self._persistence.append(self._session_id, entry)
        except Exception as exc:  # noqa: BLE001 - typed error, no fabricated history
            await self.emit(ErrorEvent(code="persistence_failed", message=f"human entry: {exc}"))
            return None

    async def finalize_assistant(self, interrupted: bool) -> str | None:
        """Write one terminal ASSISTANT entry at most; the winner's entry id.

        Returns the entry id when *this* call finalized (so it is the one that
        emits ``TurnComplete``), or ``None`` when nothing was emitted, a
        persistence failure occurred, or another path already finalized.
        """
        if self._assistant_finalized:
            return None
        self._assistant_finalized = True
        text = self._emitted_caption
        if not text:
            return None
        status = VoiceEntryStatus.INTERRUPTED if interrupted else VoiceEntryStatus.COMPLETED
        entry = VoiceEntry(kind=VoiceEntryKind.ASSISTANT, text=text, status=status)
        try:
            entry_id = await self._persistence.append(self._session_id, entry)
        except Exception as exc:  # noqa: BLE001 - typed error, no fabricated history
            await self.emit(
                ErrorEvent(code="persistence_failed", message=f"assistant entry: {exc}")
            )
            return None
        self._assistant_entry_id = entry_id
        return entry_id

    @property
    def assistant_entry_id(self) -> str | None:
        return self._assistant_entry_id


# --------------------------------------------------------------------------- #
# Pipeline bridges
# --------------------------------------------------------------------------- #


class SttBridge(FrameProcessor):
    """Feed the audio to the STT adapter and stream its transcripts downstream."""

    def __init__(self, turn: VoiceTurn) -> None:
        super().__init__(enable_direct_mode=True)
        self._turn = turn

    async def process_frame(self, frame, _direction):
        if isinstance(frame, AudioRawFrame):
            try:
                async for text, is_final in self._turn._stt.stream(frame.audio):
                    if self._turn._interrupted:
                        break
                    await self.queue_frame(
                        TranscriptionFrame(text, "onecx", "onecx", finalized=is_final)
                    )
            except Exception as exc:  # noqa: BLE001 - surfaced as a typed STT failure
                await self._turn.emit(
                    ErrorEvent(code="stt_failed", message=f"transcription failed: {exc}")
                )
                self._turn._terminal.set()
                return
            # End of the stream: drain the pipeline even with no final transcript.
            await self.queue_frame(EndFrame())
        else:
            await self.push_frame(frame, FrameDirection.DOWNSTREAM)


class TtsBridge(FrameProcessor):
    """Stream transcripts, persist the human entry, and drive the assistant audio."""

    def __init__(self, turn: VoiceTurn) -> None:
        super().__init__(enable_direct_mode=True)
        self._turn = turn
        self._saw_final = False

    async def process_frame(self, frame, _direction):
        if isinstance(frame, TranscriptionFrame):
            if frame.finalized:
                await self._on_final(frame.text)
            else:
                # Partials stream to the client and are never persisted.
                await self._turn.emit(Transcript(text=frame.text, state="PARTIAL"))
            await self.push_frame(frame, FrameDirection.DOWNSTREAM)
        elif isinstance(frame, InterruptionFrame):
            await self._on_interruption()
            await self.push_frame(frame, FrameDirection.DOWNSTREAM)
        elif isinstance(frame, EndFrame):
            # STT finished; if there was no final transcript, end the turn
            # silently (noise-only / empty input stays ephemeral).
            if not self._saw_final and not self._turn._interrupted:
                self._turn._terminal.set()
            await self.push_frame(frame, FrameDirection.DOWNSTREAM)
        else:
            await self.push_frame(frame, FrameDirection.DOWNSTREAM)

    async def _on_final(self, transcript: str) -> None:
        self._saw_final = True
        if self._turn._interrupted:
            # A barge-in already finalized this turn; do not speak over it.
            return
        await self._turn.emit(Transcript(text=transcript, state="FINAL"))
        human_id = await self._turn.persist_human(transcript)
        if human_id is None:
            # Persistence failed (typed error already emitted): do not fabricate
            # the assistant turn or a completion event.
            self._turn._terminal.set()
            return
        # Emit the caption, then stream the assistant audio incrementally.
        reply = f"heard: {transcript}"
        self._turn.set_emitted_caption(reply)
        await self._turn.emit(AssistantText(text=reply, status="COMPLETED"))
        self._turn._audio_task = asyncio.create_task(self._stream_audio(reply))

    async def _stream_audio(self, text: str) -> None:
        try:
            async for chunk in self._turn._tts.stream(text):
                if self._turn._interrupted:
                    return
                await self._turn.emit(
                    AssistantAudio(
                        audio=base64.b64encode(chunk).decode("ascii"), state="SYNTHESIZING"
                    )
                )
        except Exception as exc:  # noqa: BLE001 - TTS failure keeps the text
            await self._turn.emit(AssistantAudio(audio="", state="FAILED"))
            await self._turn.emit(ErrorEvent(code="tts_failed", message=f"synthesis failed: {exc}"))
        # Natural completion (a barge-in already finalized the entry instead):
        # persist the assistant entry, then report the turn complete only after
        # persistence has succeeded.
        if self._turn._interrupted:
            return
        entry_id = await self._turn.finalize_assistant(interrupted=False)
        if entry_id is not None:
            await self._turn.emit(TurnComplete(entry_id=entry_id))
        self._turn._terminal.set()

    async def _on_interruption(self) -> None:
        self._turn._interrupted = True
        audio_task = self._turn._audio_task
        if audio_task is not None and not audio_task.done():
            audio_task.cancel()
            try:
                await audio_task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
        # Barge-in finalizes the assistant entry from whatever was emitted so
        # far; nothing is written when nothing was emitted.
        entry_id = await self._turn.finalize_assistant(interrupted=True)
        if entry_id is not None:
            await self._turn.emit(TurnComplete(entry_id=entry_id))
        self._turn._terminal.set()
