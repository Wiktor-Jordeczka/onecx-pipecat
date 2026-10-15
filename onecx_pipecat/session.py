"""Transport-neutral voice-session state machine.

``VoiceSession`` consumes typed commands and returns typed events using the
replaceable adapters. It knows nothing about WebSocket, JSON, or FastAPI, so
the same logic drives any transport.

Starting a session is the whole authentication story: the ``start_session``
message carries the user's OneCX tokens (never the URL), and the session
verifies the token, loads the chat as the user, checks the user's voice
permission, pins the agent configuration, discovers MCP tools once, and
advertises only the tools resolved to ``ALWAYS_ALLOW`` — each step failing
closed with a typed ``ErrorEvent``.
"""

from __future__ import annotations

import base64
from enum import StrEnum

from onecx_pipecat.adapters.agent_config import AgentConfigError
from onecx_pipecat.adapters.auth import AuthenticationError
from onecx_pipecat.adapters.chat import Chat, ChatAccessError
from onecx_pipecat.adapters.permission import allowed_tools
from onecx_pipecat.container import AppContainer
from onecx_pipecat.models import (
    AgentConfigSnapshot,
    AgentToolSnapshot,
    Principal,
    VoiceEntry,
    VoiceEntryKind,
)
from onecx_pipecat.protocol import (
    AssistantAudio,
    AssistantText,
    ClientAudio,
    Command,
    DegradedCapability,
    ErrorEvent,
    Event,
    RefreshToken,
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
    """One focused voice session for one authenticated principal.

    The session's identity and tokens are established by the first
    ``start_session`` message, so the session is constructed before (and
    independently of) authentication.
    """

    def __init__(self, session_id: str, container: AppContainer) -> None:
        self.session_id = session_id
        self.state = SessionState.CREATED
        self._container = container
        self._principal: Principal | None = None
        self._apm_principal_token: str = ""
        self._authorization: str = ""
        self._snapshot: AgentConfigSnapshot | None = None
        self._chat: Chat | None = None
        self._allowed_tools: list[AgentToolSnapshot] = []

    # -- session identity -------------------------------------------------

    @property
    def principal(self) -> Principal | None:
        return self._principal

    @property
    def snapshot(self) -> AgentConfigSnapshot | None:
        return self._snapshot

    @property
    def allowed_tools(self) -> list[AgentToolSnapshot]:
        return list(self._allowed_tools)

    @property
    def apm_principal_token(self) -> str:
        return self._apm_principal_token

    async def dispatch(self, command: Command) -> list[Event]:
        match command:
            case StartSession():
                return await self._start(
                    command.agent_id,
                    command.chat_id,
                    command.apm_principal_token,
                    command.authorization,
                )
            case ClientAudio():
                return await self._audio(command.audio)
            case RefreshToken():
                return await self._refresh(command.apm_principal_token, command.authorization)
            case StopSession():
                return self._stop()
        return [ErrorEvent(code="unknown_command", message="unsupported command")]

    async def _start(
        self,
        agent_id: str,
        chat_id: str,
        apm_principal_token: str,
        authorization: str,
    ) -> list[Event]:
        if self.state is not SessionState.CREATED:
            return [ErrorEvent(code="illegal_state", message="session already started")]

        # 1. Authenticate the token carried by the message (never the URL).
        try:
            principal = await self._container.auth.authenticate(apm_principal_token)
        except AuthenticationError as exc:
            return [ErrorEvent(code="authentication_failed", message=str(exc))]
        self._principal = principal
        self._apm_principal_token = apm_principal_token
        self._authorization = authorization

        # 2. Load the chat as the user; fail closed if missing/inaccessible.
        try:
            chat = await self._container.chat.load(chat_id, apm_principal_token)
        except ChatAccessError as exc:
            return [ErrorEvent(code="chat_not_accessible", message=str(exc))]
        self._chat = chat

        # 3. Check the user's existing OneCX voice permission.
        if not await self._container.permission.has_voice_permission(
            principal, apm_principal_token
        ):
            return [
                ErrorEvent(code="voice_not_permitted", message="user lacks the voice permission")
            ]

        # 4. Pin the agent configuration for the whole session.
        try:
            snapshot = await self._container.agent_config.pin(
                principal.tenant_id, agent_id, apm_principal_token
            )
        except AgentConfigError as exc:
            # Fail closed: a new session without valid configuration cannot start.
            return [ErrorEvent(code="config_unavailable", message=str(exc))]
        self._snapshot = snapshot

        # 5. Discover tools once on the agent's own MCP servers, propagating the token.
        discovery = await self._container.mcp.discover(snapshot.mcp_servers, apm_principal_token)

        # 6. Advertise only tools the pinned configuration resolves to ALWAYS_ALLOW.
        self._allowed_tools = allowed_tools(snapshot, discovery.tools)

        self.state = SessionState.READY
        events: list[Event] = [
            SessionReady(
                session_id=self.session_id,
                agent_id=snapshot.agent_id,
                schema_version=snapshot.schema_version,
            )
        ]
        # 7. Report each skipped MCP server; the session continues degraded.
        for server_name, reason in discovery.degraded:
            events.append(DegradedCapability(reason=f"{server_name}: {reason}"))
        return events

    async def _refresh(self, apm_principal_token: str, authorization: str) -> list[Event]:
        """Replace the session tokens; fail closed if the new token is invalid."""
        if self.state is not SessionState.READY:
            return [ErrorEvent(code="illegal_state", message="session is not active")]
        try:
            principal = await self._container.auth.refresh(apm_principal_token)
        except AuthenticationError as exc:
            return [ErrorEvent(code="authentication_failed", message=str(exc))]
        self._principal = principal
        self._apm_principal_token = apm_principal_token
        self._authorization = authorization
        return []

    async def _audio(self, audio: bytes) -> list[Event]:
        if self.state is not SessionState.READY:
            return [ErrorEvent(code="illegal_state", message="session is not listening")]

        # Expired tokens end the session with a typed error.
        if self._container.auth.is_expired(self._apm_principal_token):
            self.state = SessionState.CLOSED
            return [
                ErrorEvent(code="token_expired", message="session tokens expired without refresh"),
                SessionClosed(reason="token_expired"),
            ]

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
