import pytest

from onecx_pipecat.adapters import (
    InMemoryAgentConfigAdapter,
    InMemoryAuthAdapter,
    InMemoryMcpAdapter,
    InMemoryPermissionAdapter,
    InMemoryPersistence,
    InMemorySttAdapter,
    InMemoryTtsAdapter,
)
from onecx_pipecat.adapters.auth import AuthenticationError
from onecx_pipecat.adapters.mcp import McpToolResult
from onecx_pipecat.config import McpSettings, PermissionSettings, PersistenceSettings
from onecx_pipecat.models import (
    ExecutionPolicy,
    PermissionAction,
    PermissionDecisionStatus,
    ToolProposal,
    VoiceEntry,
    VoiceEntryKind,
)


async def test_auth_unknown_token_raises():
    auth = InMemoryAuthAdapter()
    with pytest.raises(AuthenticationError):
        await auth.authenticate("nope")


async def test_auth_seeded_token_returns_principal():
    auth = InMemoryAuthAdapter()
    auth.seed("t1", "user-1", "acme", ["operator"])
    p = await auth.authenticate("t1")
    assert p.subject == "user-1"
    assert p.tenant_id == "acme"
    assert p.roles == ["operator"]


async def test_agent_config_pins_highest_version():
    cfg = InMemoryAgentConfigAdapter()
    cfg.register("acme", "a", version=1, system_prompt="v1", tool_names=["w.get"])
    cfg.register("acme", "a", version=2, system_prompt="v2", tool_names=["w.get", "w.set"])
    snap = await cfg.pin("acme", "a")
    assert snap.version == 2
    assert snap.system_prompt == "v2"


async def test_stt_tts_are_deterministic():
    stt = InMemorySttAdapter()
    tts = InMemoryTtsAdapter()
    text = await stt.transcribe(b"0" * 1024)
    assert text == "in-memory transcript"
    audio = await tts.synthesize(text)
    assert audio == text.encode("utf-8")


async def test_persistence_round_trip():
    store = InMemoryPersistence()
    entry = VoiceEntry(kind=VoiceEntryKind.HUMAN, text="hi", idempotency_key="k1")
    entry_id = await store.append("s1", entry)
    entries = await store.list_entries("s1")
    assert len(entries) == 1
    fetched = await store.get("s1", entry_id)
    assert fetched is not None and fetched.text == "hi"


async def test_permission_exact_rule_wins():
    perm = InMemoryPermissionAdapter()
    perm.set_rule("send_email", PermissionAction.ALWAYS_ASK)
    proposal = ToolProposal(
        proposal_id="p1",
        tool_name="send_email",
        arguments={"to": "a@b.c"},
        status=PermissionDecisionStatus.PENDING,
    )
    decision = await perm.evaluate(proposal)
    assert decision.action is PermissionAction.ALWAYS_ASK
    assert decision.reason == "agent tool rule"


async def test_permission_exact_rule_can_deny_or_allow():
    perm = InMemoryPermissionAdapter()
    perm.set_rule("drop_table", PermissionAction.DENY)
    perm.set_rule("list_items", PermissionAction.ALLOW)
    assert (await perm.evaluate(ToolProposal(proposal_id="p1", tool_name="drop_table"))).action is (
        PermissionAction.DENY
    )
    assert (await perm.evaluate(ToolProposal(proposal_id="p2", tool_name="list_items"))).action is (
        PermissionAction.ALLOW
    )


async def test_permission_falls_back_to_server_default_ask():
    perm = InMemoryPermissionAdapter()
    perm.set_server_default(ExecutionPolicy.ALWAYS_ASK)
    decision = await perm.evaluate(ToolProposal(proposal_id="p1", tool_name="unruled"))
    assert decision.action is PermissionAction.ALWAYS_ASK
    assert decision.reason == "server default policy"


async def test_permission_server_default_never_ask_maps_to_allow():
    """Legacy ``NEVER_ASK`` server default means auto-allow."""
    perm = InMemoryPermissionAdapter()
    perm.set_server_default(ExecutionPolicy.NEVER_ASK)
    decision = await perm.evaluate(ToolProposal(proposal_id="p1", tool_name="unruled"))
    assert decision.action is PermissionAction.ALLOW


async def test_permission_global_default_applies_without_rule_or_server_default():
    """With no rule and no server default, the configured global default applies."""
    perm = InMemoryPermissionAdapter()
    decision = await perm.evaluate(ToolProposal(proposal_id="p1", tool_name="unruled"))
    assert decision.action is PermissionAction.ALWAYS_ASK
    assert decision.reason == "global default policy"


async def test_permission_global_default_deny_denies_unruled_tool():
    """`permission.default_action=deny` denies a tool with no rule/server default."""
    perm = InMemoryPermissionAdapter(PermissionSettings(default_action="deny"))
    decision = await perm.evaluate(ToolProposal(proposal_id="p1", tool_name="unruled"))
    assert decision.action is PermissionAction.DENY


async def test_persistence_evicts_oldest_entry_when_cap_exceeded():
    store = InMemoryPersistence(PersistenceSettings(max_entries_per_session=3))
    for i in range(5):
        entry = VoiceEntry(
            kind=VoiceEntryKind.HUMAN,
            text=f"m{i}",
            idempotency_key=f"k{i}",
        )
        await store.append("s1", entry)
    entries = await store.list_entries("s1")
    assert len(entries) == 3
    # The oldest two entries (m0, m1) are evicted; the newest three remain.
    assert [e.text for e in entries] == ["m2", "m3", "m4"]


async def test_persistence_eviction_is_per_session():
    store = InMemoryPersistence(PersistenceSettings(max_entries_per_session=2))
    for i in range(3):
        await store.append("s1", VoiceEntry(kind=VoiceEntryKind.HUMAN, text=f"a{i}"))
    await store.append("s2", VoiceEntry(kind=VoiceEntryKind.HUMAN, text="s2-0"))
    assert [e.text for e in await store.list_entries("s1")] == ["a1", "a2"]
    assert [e.text for e in await store.list_entries("s2")] == ["s2-0"]


async def test_mcp_unknown_tool_is_sanitized_failure():
    mcp = InMemoryMcpAdapter()
    result = await mcp.invoke(ToolProposal(proposal_id="p1", tool_name="missing"))
    assert result.ok is False
    assert "unknown tool" in result.error
    assert isinstance(result, McpToolResult)


async def test_mcp_registered_tool_succeeds():
    mcp = InMemoryMcpAdapter()

    async def echo(args):
        return {"echo": args}

    mcp.register("echo", echo)
    result = await mcp.invoke(ToolProposal(proposal_id="p1", tool_name="echo"), {"x": 1})
    assert result.ok is True
    assert result.value == {"echo": {"x": 1}}


async def test_mcp_invoke_with_only_proposal_uses_arguments():
    """Regression test: omitting args parameter should use proposal.arguments.

    When a caller omits the args parameter (using the default None),
    the adapter should fall back to proposal.arguments instead of
    silently losing the tool's payload.
    """
    mcp = InMemoryMcpAdapter()

    async def echo(args):
        return {"echo": args}

    mcp.register("echo", echo)
    # Invoke with only proposal, no args parameter
    proposal = ToolProposal(
        proposal_id="p1",
        tool_name="echo",
        arguments={"x": 1, "y": "test"},
    )
    result = await mcp.invoke(proposal)  # args defaults to None
    assert result.ok is True
    assert result.value == {"echo": {"x": 1, "y": "test"}}


async def test_mcp_supports_multiple_servers():
    mcp = InMemoryMcpAdapter(
        McpSettings(
            default_server_name="alpha",
            servers={"alpha": "inmemory://alpha", "beta": "inmemory://beta"},
        )
    )

    async def alpha_echo(args):
        return {"server": "alpha", "echo": args}

    async def beta_echo(args):
        return {"server": "beta", "echo": args}

    mcp.register("echo", alpha_echo, server_name="alpha")
    mcp.register("echo", beta_echo, server_name="beta")

    default_result = await mcp.invoke(ToolProposal(proposal_id="p1", tool_name="echo"), {"x": 1})
    beta_result = await mcp.invoke(
        ToolProposal(proposal_id="p2", tool_name="echo", server_name="beta"),
        {"x": 2},
    )

    assert default_result.ok is True
    assert default_result.value == {"server": "alpha", "echo": {"x": 1}}
    assert beta_result.ok is True
    assert beta_result.value == {"server": "beta", "echo": {"x": 2}}


async def test_mcp_unknown_server_is_sanitized_failure():
    mcp = InMemoryMcpAdapter(
        McpSettings(default_server_name="alpha", servers={"alpha": "inmemory://alpha"})
    )
    result = await mcp.invoke(
        ToolProposal(proposal_id="p1", tool_name="echo", server_name="beta"),
        {"x": 1},
    )
    assert result.ok is False
    assert "unknown MCP server" in result.error
