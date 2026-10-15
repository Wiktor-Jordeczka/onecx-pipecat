from onecx_pipecat.models import (
    AgentConfigSnapshot,
    AgentToolSnapshot,
    ExecutionPolicy,
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


def test_permission_action_uses_canonical_vocabulary():
    assert [a.value for a in PermissionAction] == ["DENY", "ALWAYS_ASK", "ALWAYS_ALLOW"]
    # The legacy ALLOW / NEVER_ASK values are gone.
    assert not hasattr(PermissionAction, "ALLOW")
    assert not hasattr(ExecutionPolicy, "NEVER_ASK")


def test_execution_policy_uses_canonical_vocabulary():
    assert [p.value for p in ExecutionPolicy] == ["DENY", "ALWAYS_ASK", "ALWAYS_ALLOW"]


def test_agent_config_snapshot_defaults_voice_enabled_and_unlisted_permission():
    s = AgentConfigSnapshot(agent_id="a", version=3)
    assert s.voice_enabled is True
    assert s.unlisted_tool_permission is PermissionAction.ALWAYS_ASK


def test_agent_config_snapshot_is_pinned():
    s = AgentConfigSnapshot(
        agent_id="a",
        version=3,
        tool_names=["w.get"],
        tools=[
            AgentToolSnapshot(
                tool_id="tool-1",
                tool_name="w.get",
                execution_policy=ExecutionPolicy.ALWAYS_ASK,
            )
        ],
    )
    assert s.version == 3
    assert s.tool_names == ["w.get"]
    assert s.tools[0].tool_name == "w.get"
