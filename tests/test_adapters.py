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
from onecx_pipecat.config import PermissionSettings, PersistenceSettings
from onecx_pipecat.models import (
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


async def test_permission_write_tool_always_asks():
    perm = InMemoryPermissionAdapter()
    proposal = ToolProposal(
        proposal_id="p1",
        tool_name="write_record",
        arguments={"id": "1"},
        status=PermissionDecisionStatus.PENDING,
    )
    decision = await perm.evaluate(proposal)
    assert decision.action is PermissionAction.ALWAYS_ASK


async def test_permission_default_action_applies_to_non_write_tool():
    """A non-write-prefixed tool falls back to the configured default_action.

    Default is always_ask (the documented default), so an unset default still
    asks. This pins the field as load-bearing regardless of the default value.
    """
    perm = InMemoryPermissionAdapter()
    proposal = ToolProposal(proposal_id="p1", tool_name="read_record")
    decision = await perm.evaluate(proposal)
    assert decision.action is PermissionAction.ALWAYS_ASK


async def test_permission_default_deny_denies_non_write_tool():
    """`permission.default_action=deny` makes a non-write tool DENY."""
    perm = InMemoryPermissionAdapter(PermissionSettings(default_action="deny"))
    proposal = ToolProposal(proposal_id="p1", tool_name="read_record")
    decision = await perm.evaluate(proposal)
    assert decision.action is PermissionAction.DENY


async def test_permission_write_tool_still_always_asks_under_default_deny():
    """Write-prefixed tools stay ALWAYS_ASK even when the default is deny."""
    perm = InMemoryPermissionAdapter(PermissionSettings(default_action="deny"))
    proposal = ToolProposal(proposal_id="p1", tool_name="write_record")
    decision = await perm.evaluate(proposal)
    assert decision.action is PermissionAction.ALWAYS_ASK


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
