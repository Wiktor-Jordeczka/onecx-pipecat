"""Transport-neutral voice-session state machine.

``VoiceSession`` consumes typed commands and returns typed events using the
replaceable adapters. It knows nothing about WebSocket, JSON, or FastAPI, so
the same logic drives any transport.
"""

from __future__ import annotations

import base64
from enum import StrEnum

from onecx_pipecat.adapters.agent_config import AgentConfigError
from onecx_pipecat.container import AppContainer
from onecx_pipecat.models import Principal, VoiceEntry, VoiceEntryKind
from onecx_pipecat.protocol import (
    AssistantAudio,
    AssistantText,
    ClientAudio,
    Command,
    ErrorEvent,
    Event,
    SessionClosed,
    SessionReady,
    StartSession,
    StopSession,
    Transcript,
    TurnComplete,
)


class SessionState(StrEnum):
    CREATED = "CREATED"
    READY = "READY"
    CLOSED = "CLOSED"


class VoiceSession:
    """One focused voice session for one authenticated principal."""

    def __init__(self, session_id: str, principal: Principal, container: AppContainer) -> None:
        self.session_id = session_id
        self.state = SessionState.CREATED
        self._principal = principal
        self._container = container

    async def dispatch(self, command: Command) -> list[Event]:
        match command:
            case StartSession():
                return await self._start(command.agent_id)
            case ClientAudio():
                return await self._audio(command.audio)
            case StopSession():
                return self._stop()
        return [ErrorEvent(code="unknown_command", message="unsupported command")]

    async def _start(self, agent_id: str) -> list[Event]:
        if self.state is not SessionState.CREATED:
            return [ErrorEvent(code="illegal_state", message="session already started")]
        try:
            snapshot = await self._container.agent_config.pin(self._principal.tenant_id, agent_id)
        except AgentConfigError as exc:
            # Fail closed: a new session without valid configuration cannot start.
            return [ErrorEvent(code="config_unavailable", message=str(exc))]
        self.state = SessionState.READY
        return [
            SessionReady(
                session_id=self.session_id,
                agent_id=snapshot.agent_id,
                agent_version=snapshot.version,
            )
        ]

    async def _audio(self, audio: bytes) -> list[Event]:
        if self.state is not SessionState.READY:
            return [ErrorEvent(code="illegal_state", message="session is not listening")]

        transcript = await self._container.stt.transcribe(audio)
        if not transcript:
            # Partial, abandoned, and noise-only input stays ephemeral.
            return []

        events: list[Event] = [Transcript(text=transcript, state="FINAL")]
        await self._container.persistence.append(
            self.session_id, VoiceEntry(kind=VoiceEntryKind.HUMAN, text=transcript)
        )

        reply = f"heard: {transcript}"
        events.append(AssistantText(text=reply, status="COMPLETED"))
        entry_id = await self._container.persistence.append(
            self.session_id, VoiceEntry(kind=VoiceEntryKind.ASSISTANT, text=reply)
        )

        try:
            audio_out = await self._container.tts.synthesize(reply)
            events.append(
                AssistantAudio(audio=base64.b64encode(audio_out).decode("ascii"), state="COMPLETE")
            )
        except Exception:  # noqa: BLE001 - TTS failure must not discard the answer
            events.append(AssistantAudio(audio="", state="FAILED"))

        events.append(TurnComplete(entry_id=entry_id))
        return events

    def _stop(self) -> list[Event]:
        self.state = SessionState.CLOSED
        return [SessionClosed(reason="client_stopped")]
