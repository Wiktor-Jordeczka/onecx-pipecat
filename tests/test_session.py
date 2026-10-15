from onecx_pipecat.container import AppContainer
from onecx_pipecat.models import (
    AgentConfigSnapshot,
    McpServerSnapshot,
    PermissionAction,
    Principal,
    ToolRule,
    VoiceEntryKind,
)
from onecx_pipecat.protocol import ClientAudio, RefreshToken, StartSession, StopSession
from onecx_pipecat.session import SessionState, VoiceSession
from tests.fakes import FakeAgentConfig, fake_container


def _container() -> AppContainer:
    return fake_container()


def _start(**overrides) -> StartSession:
    kwargs = {"agent_id": "onecx-agent", "chat_id": "chat-1", "apm_principal_token": "tok-user"}
    kwargs.update(overrides)
    return StartSession(**kwargs)


def _session(container: AppContainer) -> VoiceSession:
    return VoiceSession("sess-1", container)


async def test_start_becomes_ready_with_pinned_configuration():
    session = _session(_container())
    events = await session.dispatch(_start())
    assert session.state is SessionState.READY
    assert [e.kind for e in events] == ["session_ready"]
    assert events[0].schema_version == "1"
    assert session.snapshot is not None and session.snapshot.system_prompt == "be brief"


async def test_start_without_configuration_fails_closed():
    container = _container()
    container.agent_config = FakeAgentConfig()
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
    container.permission.deny_voice("user-1")
    session = _session(container)
    events = await session.dispatch(_start())
    assert session.state is SessionState.CREATED
    assert events[0].kind == "error"
    assert events[0].code == "voice_not_permitted"


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


def _snapshot_with_servers() -> AgentConfigSnapshot:
    return AgentConfigSnapshot(
        agent_id="onecx-agent",
        schema_version="1",
        mcp_servers=[
            McpServerSnapshot(
                name="crm",
                url="https://crm.example/mcp",
                unlisted_tool_permission=PermissionAction.DENY,
                tool_rules=[
                    ToolRule(tool_name="safe", permission=PermissionAction.ALWAYS_ALLOW),
                    ToolRule(tool_name="asked", permission=PermissionAction.ALWAYS_ASK),
                ],
            ),
            McpServerSnapshot(
                name="docs",
                url="https://docs.example/mcp",
                unlisted_tool_permission=PermissionAction.ALWAYS_ALLOW,
            ),
        ],
    )


async def test_discovery_uses_the_agents_servers_and_token():
    """MCP servers come from the pinned agent configuration, not global settings."""
    container = _container()
    container.agent_config.register(_snapshot_with_servers())
    session = _session(container)
    await session.dispatch(_start())
    assert container.mcp.calls == [(["crm", "docs"], "tok-user")]


async def test_start_filters_to_always_allow_tools_only():
    container = _container()
    container.agent_config.register(_snapshot_with_servers())
    container.mcp.tools = {"crm": ["safe", "asked", "listed"], "docs": ["search"]}
    session = _session(container)
    await session.dispatch(_start())
    # crm: "safe" is ALWAYS_ALLOW, "asked" ALWAYS_ASK, "listed" falls to DENY;
    # docs: "search" has no rule and falls to that server's ALWAYS_ALLOW.
    assert [(t.server_name, t.tool_name) for t in session.allowed_tools] == [
        ("crm", "safe"),
        ("docs", "search"),
    ]


async def test_start_emits_degraded_capability_for_failed_server():
    container = _container()
    container.agent_config.register(_snapshot_with_servers())
    container.mcp.failures = {"crm": "connection refused"}
    session = _session(container)
    events = await session.dispatch(_start())
    kinds = [e.kind for e in events]
    assert kinds == ["session_ready", "degraded_capability"]
    assert "crm" in events[1].reason


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
