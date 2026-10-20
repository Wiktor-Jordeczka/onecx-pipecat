"""Transport-neutral voice-session state machine.

``VoiceSession`` consumes typed commands and returns typed events using the
replaceable adapters. It knows nothing about WebSocket, JSON, or FastAPI, so
the same logic drives any transport.

Each voice turn runs in the background on a real Pipecat pipeline (see
:mod:`onecx_pipecat.voice_turn`), streaming its events — partial/final
transcript, the assistant caption, and the incrementally synthesized audio —
through an event sink installed with :meth:`VoiceSession.set_event_sink`. The
turn finalizes every durable entry in a terminal state; a second user utterance
interrupts the in-flight assistant output (barge-in), and the session releases
its pipeline and adapter resources when stopped or disconnected.

Starting a session is the whole authentication story: the ``start_session``
message carries the user's OneCX tokens (never the URL), and the session
verifies the token, loads the chat as the user, checks the user's voice
permission, pins the agent configuration, discovers MCP tools once, and
advertises only the tools resolved to ``ALWAYS_ALLOW`` — each step failing
closed with a typed ``ErrorEvent``.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from enum import StrEnum
from typing import Any
from uuid import uuid4

from onecx_pipecat.adapters.agent_config import AgentConfigError
from onecx_pipecat.adapters.auth import AuthenticationError
from onecx_pipecat.adapters.chat import Chat, ChatAccessError
from onecx_pipecat.adapters.factory import build_stt, build_tts
from onecx_pipecat.adapters.mcp import McpToolResult, propagated_headers
from onecx_pipecat.adapters.permission import allowed_tools
from onecx_pipecat.adapters.speech import UnsupportedLanguageError
from onecx_pipecat.container import AppContainer
from onecx_pipecat.models import (
    AgentConfigSnapshot,
    AgentToolSnapshot,
    Principal,
    ToolProposal,
)
from onecx_pipecat.protocol import (
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
)
from onecx_pipecat.voice_turn import VoiceTurn


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
        self._start_failed = False
        # Streaming events (captions, audio) flow out of the background turn
        # through this sink instead of being returned by ``dispatch``.
        self._event_sink: Callable[[Event], Awaitable[None]] | Callable[[Event], None] | None = None
        self._active_turn: VoiceTurn | None = None
        # Every in-flight turn task, not just the newest: a barge-in starts a new
        # turn while the interrupted one is still cleaning up its pipeline, and
        # a stop/disconnect must wait for each of them to release its resources.
        self._turn_tasks: set[asyncio.Task[None]] = set()

    def set_event_sink(
        self, sink: Callable[[Event], Awaitable[None]] | Callable[[Event], None] | None
    ) -> None:
        """Install the transport sink streaming voice-turn events out of the session."""
        self._event_sink = sink

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
        if self.state is SessionState.READY and not isinstance(
            command, (RefreshToken, StopSession)
        ):
            if expired := self.check_expiry():
                return expired
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
                return await self._stop()
        return [ErrorEvent(code="unknown_command", message="unsupported command")]

    @property
    def start_failed(self) -> bool:
        """True when the session was closed because ``start_session`` was rejected."""
        return self._start_failed

    def check_expiry(self) -> list[Event]:
        """End a READY session whose tokens have expired; no-op otherwise."""
        if self.state is not SessionState.READY:
            return []
        if not self._container.auth.is_expired(self._apm_principal_token):
            return []
        self.state = SessionState.CLOSED
        return [
            ErrorEvent(code="token_expired", message="session tokens expired without refresh"),
            SessionClosed(reason="token_expired"),
        ]

    async def invoke_tool(
        self, server_name: str, tool_name: str, arguments: dict[str, Any] | None = None
    ) -> McpToolResult:
        """Invoke a tool, but only one the pinned configuration resolved to ALWAYS_ALLOW."""
        if self.state is not SessionState.READY or self._snapshot is None:
            return McpToolResult(ok=False, error="session is not active")
        permitted = any(
            tool.server_name == server_name and tool.tool_name == tool_name
            for tool in self._allowed_tools
        )
        server = next((s for s in self._snapshot.mcp_servers if s.name == server_name), None)
        if not permitted or server is None:
            return McpToolResult(ok=False, error=f"tool {tool_name!r} is not permitted")
        proposal = ToolProposal(
            proposal_id=uuid4().hex,
            tool_name=tool_name,
            server_name=server_name,
            arguments=dict(arguments or {}),
        )
        return await self._container.mcp.invoke(
            server, proposal, propagated_headers(self._apm_principal_token, self._authorization)
        )

    def _reset(self) -> None:
        """Drop everything a half-finished start may have established."""
        self._principal = None
        self._apm_principal_token = ""
        self._authorization = ""
        self._snapshot = None
        self._chat = None
        self._allowed_tools = []

    def _fail_start(self, code: str, message: str) -> list[Event]:
        self._reset()
        self.state = SessionState.CLOSED
        self._start_failed = True
        return [ErrorEvent(code=code, message=message), SessionClosed(reason="start_failed")]

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
            return self._fail_start("authentication_failed", str(exc))
        self._principal = principal
        self._apm_principal_token = apm_principal_token
        self._authorization = authorization

        # 2. Load the chat; fail closed if missing/inaccessible or not the user's.
        try:
            chat = await self._container.chat.load(chat_id, apm_principal_token)
        except ChatAccessError as exc:
            return self._fail_start("chat_not_accessible", str(exc))
        if principal.subject not in chat.user_ids:
            return self._fail_start("chat_not_accessible", f"chat {chat_id!r} not accessible")
        self._chat = chat

        # 3. Check the user's existing OneCX voice permission.
        if not await self._container.permission.has_voice_permission(
            principal, apm_principal_token
        ):
            return self._fail_start("voice_not_permitted", "user lacks the voice permission")

        # 4. Pin the agent configuration for the whole session.
        try:
            snapshot = await self._container.agent_config.pin(
                principal.tenant_id, agent_id, apm_principal_token
            )
        except AgentConfigError as exc:
            # Fail closed: a new session without valid configuration cannot start.
            return self._fail_start("config_unavailable", str(exc))
        self._snapshot = snapshot

        # 5. Discover tools once on the agent's own MCP servers, forwarding the user's tokens.
        discovery = await self._container.mcp.discover(
            snapshot.mcp_servers, propagated_headers(apm_principal_token, authorization)
        )

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
        # A refresh extends the same user's session; it must never switch the user,
        # whose chat access and voice permission were checked only at start.
        current = self._principal
        if (
            current is None
            or principal.subject != current.subject
            or principal.tenant_id != current.tenant_id
        ):
            return [
                ErrorEvent(
                    code="principal_mismatch",
                    message="refreshed token belongs to a different user",
                )
            ]
        self._principal = principal
        self._apm_principal_token = apm_principal_token
        self._authorization = authorization
        return []

    async def _audio(self, audio: bytes) -> list[Event]:
        if self.state is not SessionState.READY:
            return [ErrorEvent(code="illegal_state", message="session is not listening")]

        if expired := self.check_expiry():
            return expired

        # A new utterance barges in on the in-flight assistant output (if any),
        # cutting it short and finalizing it as INTERRUPTED before the next turn.
        if self._active_turn is not None:
            await self._active_turn.barge_in()

        try:
            stt, tts = self._build_speech()
        except UnsupportedLanguageError as exc:
            return [ErrorEvent(code="unsupported_language", message=str(exc))]

        sink = self._event_sink or (lambda _event: None)
        turn = VoiceTurn(
            stt=stt,
            tts=tts,
            on_event=sink,
            persistence=self._container.persistence,
            session_id=self.session_id,
            sample_rate_hz=self._container.settings.speech.sample_rate_hz,
        )
        self._active_turn = turn
        task = asyncio.create_task(self._drive_turn(turn, audio))
        self._turn_tasks.add(task)
        # The turn streams its events (transcript, caption, audio, completion)
        # through the sink; ``dispatch`` returns no batch for an audio turn.
        return []

    def _build_speech(self) -> tuple[Any, Any]:
        """Build the turn's STT/TTS adapters for the pinned language.

        The in-memory provider is language-agnostic (a deterministic echo); the
        ``aws`` provider resolves the pinned language to its Transcribe/Polly
        profiles and raises ``UnsupportedLanguageError`` when none is configured.
        """
        language = self._snapshot.language_code if self._snapshot is not None else ""
        settings = self._container.settings
        return build_stt(settings, language), build_tts(settings, language)

    async def _drive_turn(self, turn: VoiceTurn, audio: bytes) -> None:
        """Run a turn in the background; a turn must never wedge the session."""
        try:
            await turn.run(audio)
        except Exception as exc:  # noqa: BLE001 - defensive: keep the session usable
            if self._event_sink is not None:
                await self._event_sink(
                    ErrorEvent(code="turn_failed", message=f"voice turn failed: {exc}")
                )
        finally:
            if self._active_turn is turn:
                self._active_turn = None
            await turn.release()
            self._turn_tasks.discard(asyncio.current_task())

    async def wait_for_turn(self) -> None:
        """Await the active turn (if any) until it reaches a terminal state."""
        if self._turn_tasks:
            await asyncio.gather(*self._turn_tasks, return_exceptions=True)

    async def release(self) -> None:
        """End the run: stop any active turn and release its pipeline resources.

        Barges in on the active turn (interrupting its output) and waits for
        every in-flight turn task to finish and release its pipeline, so a stop
        or a disconnect leaves no pipeline or adapter resources behind.
        """
        if self._active_turn is not None:
            await self._active_turn.barge_in()
            self._active_turn = None
        if self._turn_tasks:
            try:
                await asyncio.gather(*self._turn_tasks, return_exceptions=True)
            except (asyncio.CancelledError, Exception):  # noqa: BLE001 - release must not raise
                pass
            self._turn_tasks.clear()

    async def _stop(self) -> list[Event]:
        await self.release()
        self.state = SessionState.CLOSED
        return [SessionClosed(reason="client_stopped")]
