from onecx_pipecat.models import (
    AgentConfigSnapshot,
    McpServerSnapshot,
    PermissionAction,
    PermissionDecision,
    PermissionDecisionStatus,
    Principal,
    ToolProposal,
    ToolRule,
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


def test_mcp_server_without_unlisted_policy_denies_unlisted_tools():
    s = McpServerSnapshot(name="crm", url="https://crm.example/mcp")
    assert s.unlisted_tool_permission is PermissionAction.DENY
    assert s.tool_rules == []


def test_agent_config_snapshot_is_pinned():
    s = AgentConfigSnapshot(
        agent_id="a",
        schema_version="1",
        mcp_servers=[
            McpServerSnapshot(
                name="crm",
                url="https://crm.example/mcp",
                tool_rules=[ToolRule(tool_name="w.get", permission=PermissionAction.ALWAYS_ASK)],
            )
        ],
    )
    assert s.schema_version == "1"
    assert s.mcp_servers[0].tool_rules[0].tool_name == "w.get"
