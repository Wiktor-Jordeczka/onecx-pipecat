from onecx_pipecat.adapters.mcp import McpDiscovery
from onecx_pipecat.config import Settings
from onecx_pipecat.container import AppContainer
from onecx_pipecat.models import (
    AgentConfigSnapshot,
    AgentToolSnapshot,
    PermissionAction,
    Principal,
    VoiceEntryKind,
)
from onecx_pipecat.protocol import ClientAudio, RefreshToken, StartSession, StopSession
from onecx_pipecat.session import SessionState, VoiceSession


def _container() -> AppContainer:
    container = AppContainer(Settings())
    container.auth.seed("tok-user", subject="user-1", tenant_id="local", roles=["voice"])
    container.chat.register("chat-1", title="general")
    container.agent_config.register("local", "onecx-agent", 1, system_prompt="be brief")
    return container


def _start(**overrides) -> StartSession:
    kwargs = {"agent_id": "onecx-agent", "chat_id": "chat-1", "apm_principal_token": "tok-user"}
    kwargs.update(overrides)
    return StartSession(**kwargs)


def _session(container: AppContainer) -> VoiceSession:
    return VoiceSession("sess-1", container)


async def test_start_becomes_ready_with_pinned_version():
    session = _session(_container())
    events = await session.dispatch(_start())
    assert session.state is SessionState.READY
    assert [e.kind for e in events] == ["session_ready"]
    assert events[0].agent_version == 1
    assert session.snapshot is not None and session.snapshot.version == 1


async def test_start_without_configuration_fails_closed():
    container = AppContainer(Settings())
    container.auth.seed("tok-user", subject="user-1", tenant_id="local")
    container.chat.register("chat-1")
    session = _session(container)
    events = await session.dispatch(_start())
    assert session.state is SessionState.CREATED
    assert events[0].kind == "error"
    assert events[0].code == "config_unavailable"


async def test_start_with_unknown_token_fails_authentication():
    session = _session(_container())
    events = await session.dispatch(_start(apm_principal_token="nope"))
    assert session.state is SessionState.CREATED
    assert events[0].kind == "error"
    assert events[0].code == "authentication_failed"


async def test_start_with_expired_token_fails_authentication():
    container = _container()
    container.auth.mark_expired("tok-user")
    session = _session(container)
    events = await session.dispatch(_start())
    assert session.state is SessionState.CREATED
    assert events[0].code == "authentication_failed"


async def test_start_with_unknown_chat_fails():
    session = _session(_container())
    events = await session.dispatch(_start(chat_id="missing"))
    assert session.state is SessionState.CREATED
    assert events[0].kind == "error"
    assert events[0].code == "chat_not_accessible"


async def test_start_without_voice_permission_fails():
    container = _container()
    container.permission.set_voice_permission("user-1", False)
    session = _session(container)
    events = await session.dispatch(_start())
    assert session.state is SessionState.CREATED
    assert events[0].kind == "error"
    assert events[0].code == "voice_not_permitted"


async def test_start_with_voice_disabled_agent_fails():
    container = AppContainer(Settings())
    container.auth.seed("tok-user", subject="user-1", tenant_id="local")
    container.chat.register("chat-1")
    container.agent_config.register("local", "onecx-agent", 1, voice_enabled=False)
    session = _session(container)
    events = await session.dispatch(_start())
    assert session.state is SessionState.CREATED
    assert events[0].code == "config_unavailable"


async def test_start_verifies_token_from_message_not_url():
    """The token is validated against the auth adapter, not the query string."""
    seen: list[str] = []

    class RecordingAuth:
        async def authenticate(self, token: str) -> Principal:
            seen.append(token)
            return Principal(subject="user-1", tenant_id="local")

        def is_expired(self, token: str) -> bool:
            return False

        async def refresh(self, token: str) -> Principal:
            return Principal(subject="user-1", tenant_id="local")

        async def service_token(self) -> str:
            return "svc"

    container = _container()
    container.auth = RecordingAuth()  # type: ignore[assignment]
    session = _session(container)
    await session.dispatch(_start(apm_principal_token="from-message"))
    assert seen == ["from-message"]


async def test_token_propagates_to_mcp_discovery():
    """The principal token reaches the one-time MCP discovery."""
    seen: list[str] = []

    class RecordingMcp:
        async def invoke(self, proposal, args=None):
            raise NotImplementedError

        async def discover(self, apm_principal_token: str) -> McpDiscovery:
            seen.append(apm_principal_token)
            return McpDiscovery()

    container = _container()
    container.mcp = RecordingMcp()  # type: ignore[assignment]
    session = _session(container)
    await session.dispatch(_start())
    assert seen == ["tok-user"]


async def test_start_filters_to_always_allow_tools_only():
    container = _container()
    # The pinned snapshot carries the per-tool policy: "safe" is ALWAYS_ALLOW,
    # "asked" is ALWAYS_ASK; "listed" has no rule and falls to the unlisted DENY.
    snapshot = AgentConfigSnapshot(
        agent_id="onecx-agent",
        version=1,
        unlisted_tool_permission=PermissionAction.DENY,
        tools=[
            AgentToolSnapshot(tool_name="safe", allowed=PermissionAction.ALWAYS_ALLOW),
            AgentToolSnapshot(tool_name="asked", allowed=PermissionAction.ALWAYS_ASK),
        ],
    )
    discovered = [
        AgentToolSnapshot(tool_name="safe"),
        AgentToolSnapshot(tool_name="asked"),
        AgentToolSnapshot(tool_name="listed"),
    ]

    class FilteringMcp:
        async def invoke(self, proposal, args=None):
            raise NotImplementedError

        async def discover(self, apm_principal_token: str) -> McpDiscovery:
            return McpDiscovery(tools=list(discovered))

    container.mcp = FilteringMcp()  # type: ignore[assignment]

    class Pinning:
        async def pin(self, tenant_id, agent_id, apm_principal_token) -> AgentConfigSnapshot:
            return snapshot

    container.agent_config = Pinning()  # type: ignore[assignment]
    session = _session(container)
    await session.dispatch(_start())
    # Only "safe" resolves to ALWAYS_ALLOW (explicit); "asked" is ALWAYS_ASK and
    # "listed" falls to the DENY unlisted default.
    assert [t.tool_name for t in session.allowed_tools] == ["safe"]


async def test_start_emits_degraded_capability_for_failed_server():
    container = _container()
    container.mcp.mark_degraded("inmemory", "connection refused")
    session = _session(container)
    events = await session.dispatch(_start())
    kinds = [e.kind for e in events]
    assert kinds == ["session_ready", "degraded_capability"]
    assert "inmemory" in events[1].reason


async def test_refresh_replaces_session_tokens():
    container = _container()
    container.auth.seed("tok-new", subject="user-1", tenant_id="local")
    session = _session(container)
    await session.dispatch(_start())
    events = await session.dispatch(
        RefreshToken(apm_principal_token="tok-new", authorization="Bearer tok-new")
    )
    assert events == []
    assert session.apm_principal_token == "tok-new"


async def test_refresh_with_invalid_token_fails():
    session = _session(_container())
    await session.dispatch(_start())
    events = await session.dispatch(RefreshToken(apm_principal_token="bogus"))
    assert events[0].kind == "error"
    assert events[0].code == "authentication_failed"


async def test_refresh_before_start_is_rejected():
    session = _session(_container())
    events = await session.dispatch(RefreshToken(apm_principal_token="tok-user"))
    assert events[0].code == "illegal_state"


async def test_expired_tokens_end_session_with_typed_error():
    container = _container()
    session = _session(container)
    await session.dispatch(_start())
    container.auth.mark_expired("tok-user")
    events = await session.dispatch(ClientAudio(audio=b"pcm"))
    assert [e.kind for e in events] == ["error", "session_closed"]
    assert events[0].code == "token_expired"
    assert session.state is SessionState.CLOSED


async def test_audio_before_start_is_rejected():
    session = _session(_container())
    events = await session.dispatch(ClientAudio(audio=b"pcm"))
    assert events[0].kind == "error"
    assert events[0].code == "illegal_state"


async def test_second_start_is_rejected():
    session = _session(_container())
    await session.dispatch(_start())
    events = await session.dispatch(_start())
    assert events[0].kind == "error"
    assert events[0].code == "illegal_state"


async def test_audio_turn_emits_transcript_text_audio_and_completion():
    container = _container()
    session = _session(container)
    await session.dispatch(_start())
    events = await session.dispatch(ClientAudio(audio=b"pcm"))
    kinds = [e.kind for e in events]
    assert kinds == ["transcript", "assistant_text", "assistant_audio", "turn_complete"]
    assert events[0].state == "FINAL"
    assert events[1].status == "COMPLETED"


async def test_empty_transcript_stays_ephemeral():
    session = _session(_container())
    await session.dispatch(_start())
    events = await session.dispatch(ClientAudio(audio=b""))
    assert events == []


async def test_turn_persists_human_and_assistant_entries():
    container = _container()
    session = _session(container)
    await session.dispatch(_start())
    await session.dispatch(ClientAudio(audio=b"pcm"))
    entries = await container.persistence.list_entries("sess-1")
    kinds = [entry.kind for entry in entries]
    assert kinds == [VoiceEntryKind.HUMAN, VoiceEntryKind.ASSISTANT]


async def test_stop_closes_the_session():
    session = _session(_container())
    await session.dispatch(_start())
    events = await session.dispatch(StopSession())
    assert session.state is SessionState.CLOSED
    assert events[0].kind == "session_closed"
