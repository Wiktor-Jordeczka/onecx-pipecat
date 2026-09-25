from onecx_pipecat.models import (
    AgentConfigSnapshot,
    PermissionAction,
    PermissionDecision,
    PermissionDecisionStatus,
    Principal,
    ToolProposal,
    VoiceEntry,
    VoiceEntryKind,
)


def test_principal_round_trips():
    p = Principal(subject="user-1", tenant_id="acme", roles=["operator"])
    assert p.tenant_id == "acme"
    assert p.roles == ["operator"]


def test_voice_entry_hidden_default_false():
    e = VoiceEntry(kind=VoiceEntryKind.HUMAN, text="hi")
    assert e.hidden is False
    assert e.idempotency_key is None


def test_tool_proposal_defaults_to_pending():
    t = ToolProposal(proposal_id="p1", tool_name="weather.get")
    assert t.status is PermissionDecisionStatus.PENDING
    assert t.server_name is None
    assert t.arguments == {}


def test_permission_decision_carries_action():
    d = PermissionDecision(action=PermissionAction.ALWAYS_ASK, reason="write op")
    assert d.action is PermissionAction.ALWAYS_ASK
    assert "write" in d.reason


def test_agent_config_snapshot_is_pinned():
    s = AgentConfigSnapshot(agent_id="a", version=3, tool_names=["w.get"])
    assert s.version == 3
    assert s.tool_names == ["w.get"]
