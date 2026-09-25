"""Transport-neutral voice-session protocol.

Commands are what a client asks a session to do; events are what the session
emits back. The vocabulary is intentionally independent of any wire transport
so the WebSocket carrier can later be replaced (for example with WebRTC)
without changing session behavior.
"""

from __future__ import annotations

import base64
import binascii
from typing import Literal

from pydantic import BaseModel


class StartSession(BaseModel):
    """Begin a voice session against a pinned agent configuration."""

    type: Literal["start_session"] = "start_session"
    agent_id: str


class ClientAudio(BaseModel):
    """A finalized chunk of captured microphone audio."""

    type: Literal["audio"] = "audio"
    audio: bytes = b""


class StopSession(BaseModel):
    """End the voice session and return to typed chat."""

    type: Literal["stop"] = "stop"


Command = StartSession | ClientAudio | StopSession


class SessionReady(BaseModel):
    kind: Literal["session_ready"] = "session_ready"
    session_id: str
    agent_id: str
    agent_version: int


class Transcript(BaseModel):
    kind: Literal["transcript"] = "transcript"
    text: str
    state: str


class AssistantText(BaseModel):
    kind: Literal["assistant_text"] = "assistant_text"
    text: str
    status: str


class AssistantAudio(BaseModel):
    kind: Literal["assistant_audio"] = "assistant_audio"
    audio: str
    state: str


class TurnComplete(BaseModel):
    kind: Literal["turn_complete"] = "turn_complete"
    entry_id: str


class ErrorEvent(BaseModel):
    kind: Literal["error"] = "error"
    code: str
    message: str


class SessionClosed(BaseModel):
    kind: Literal["session_closed"] = "session_closed"
    reason: str


Event = (
    SessionReady
    | Transcript
    | AssistantText
    | AssistantAudio
    | TurnComplete
    | ErrorEvent
    | SessionClosed
)


def decode_command(raw: dict) -> Command | None:
    """Turn a decoded JSON object into a typed command, or None if invalid."""
    match raw.get("type"):
        case "start_session":
            agent_id = raw.get("agent_id")
            if not isinstance(agent_id, str) or not agent_id:
                return None
            return StartSession(agent_id=agent_id)
        case "audio":
            encoded = raw.get("audio", "")
            if not isinstance(encoded, str):
                return None
            try:
                audio = base64.b64decode(encoded, validate=True) if encoded else b""
            except (binascii.Error, ValueError):
                return None
            return ClientAudio(audio=audio)
        case "stop":
            return StopSession()
        case _:
            return None
