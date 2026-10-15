"""Permission adapter: evaluate a tool call and drive decisions.

Also owns session eligibility: checking the user's existing OneCX voice
permission through the existing permission interface (a distinct concern from
per-tool evaluation), and resolving which discovered tools a session may
advertise — only those whose resolved policy is ``ALWAYS_ALLOW``.
"""

from __future__ import annotations

from typing import Protocol

from onecx_pipecat.config import PermissionSettings
from onecx_pipecat.models import (
    AgentConfigSnapshot,
    AgentMcpToolRule,
    AgentToolSnapshot,
    ExecutionPolicy,
    PermissionAction,
    PermissionDecision,
    Principal,
    ToolProposal,
)


class PermissionAdapter(Protocol):
    async def evaluate(self, proposal: ToolProposal) -> PermissionDecision: ...

    async def has_voice_permission(self, principal: Principal, apm_principal_token: str) -> bool:
        """Whether the user already has the OneCX voice permission."""
        ...

    async def allowed_tools(
        self, snapshot: AgentConfigSnapshot, discovered: list[AgentToolSnapshot]
    ) -> list[AgentToolSnapshot]:
        """Discovered tools whose resolved policy is ``ALWAYS_ALLOW``."""
        ...


class InMemoryPermissionAdapter:
    """Resolve a tool's policy the way provider-svc intends: an exact per-agent
    rule wins, then the tool connection's server default, then the operator's
    global default. Policy is data, never guessed from the tool name.

    The real control plane owns these rules (``AgentMcpToolRule`` and
    ``Tool.executionPolicy``); this stand-in holds them in memory so the
    resolution order is exercisable without provider-svc.
    """

    def __init__(self, settings: PermissionSettings | None = None) -> None:
        self._settings = settings or PermissionSettings()
        self._rules: dict[str, AgentMcpToolRule] = {}
        self._server_default: ExecutionPolicy | None = None
        self._voice: dict[str, bool] = {}

    def set_rule(self, tool_name: str, allowed: PermissionAction, description: str = "") -> None:
        self._rules[tool_name] = AgentMcpToolRule(
            tool_name=tool_name, allowed=allowed, tool_description=description
        )

    def set_server_default(self, policy: ExecutionPolicy) -> None:
        self._server_default = policy

    def set_voice_permission(self, subject: str, allowed: bool) -> None:
        """Record the user's existing OneCX voice permission (test-only)."""
        self._voice[subject] = allowed

    async def has_voice_permission(self, principal: Principal, apm_principal_token: str) -> bool:
        return self._voice.get(principal.subject, True)

    def resolve(self, snapshot: AgentConfigSnapshot, tool: AgentToolSnapshot) -> PermissionAction:
        """The resolved policy for a discovered tool.

        A per-tool rule wins, then the tool's own execution policy, then the
        snapshot's ``unlisted_tool_permission`` for tools with no rule.
        """
        rule = self._rules.get(tool.tool_name)
        if rule is not None:
            return rule.allowed
        for snapshot_tool in snapshot.tools:
            if snapshot_tool.tool_name == tool.tool_name and snapshot_tool.allowed is not None:
                return snapshot_tool.allowed
        return snapshot.unlisted_tool_permission

    async def allowed_tools(
        self, snapshot: AgentConfigSnapshot, discovered: list[AgentToolSnapshot]
    ) -> list[AgentToolSnapshot]:
        """Only tools resolved to ``ALWAYS_ALLOW`` are advertised."""
        return [t for t in discovered if self.resolve(snapshot, t) is PermissionAction.ALWAYS_ALLOW]

    async def evaluate(self, proposal: ToolProposal) -> PermissionDecision:
        rule = self._rules.get(proposal.tool_name)
        if rule is not None:
            return PermissionDecision(action=rule.allowed, reason="agent tool rule")

        if self._server_default is not None:
            # The server default is already in the canonical vocabulary.
            action = PermissionAction(self._server_default.value)
            return PermissionDecision(action=action, reason="server default policy")

        # The operator's documented choice for tools with no explicit rule; it is
        # case-insensitive (config values are lowercase, enum values are uppercase).
        default_action = PermissionAction(self._settings.default_action.strip().upper())
        return PermissionDecision(action=default_action, reason="global default policy")
