"""Permission adapter: evaluate a tool call and drive decisions."""

from __future__ import annotations

from typing import Protocol

from onecx_pipecat.config import PermissionSettings
from onecx_pipecat.models import (
    AgentMcpToolRule,
    ExecutionPolicy,
    PermissionAction,
    PermissionDecision,
    ToolProposal,
)


class PermissionAdapter(Protocol):
    async def evaluate(self, proposal: ToolProposal) -> PermissionDecision: ...


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

    def set_rule(self, tool_name: str, allowed: PermissionAction, description: str = "") -> None:
        self._rules[tool_name] = AgentMcpToolRule(
            tool_name=tool_name, allowed=allowed, tool_description=description
        )

    def set_server_default(self, policy: ExecutionPolicy) -> None:
        self._server_default = policy

    async def evaluate(self, proposal: ToolProposal) -> PermissionDecision:
        rule = self._rules.get(proposal.tool_name)
        if rule is not None:
            return PermissionDecision(action=rule.allowed, reason="agent tool rule")

        if self._server_default is not None:
            # Legacy server default: NEVER_ASK means "do not ask", i.e. ALLOW.
            action = (
                PermissionAction.ALWAYS_ASK
                if self._server_default is ExecutionPolicy.ALWAYS_ASK
                else PermissionAction.ALLOW
            )
            return PermissionDecision(action=action, reason="server default policy")

        # The operator's documented choice for tools with no explicit rule; it is
        # case-insensitive (config values are lowercase, enum values are uppercase).
        default_action = PermissionAction(self._settings.default_action.strip().upper())
        return PermissionDecision(action=default_action, reason="global default policy")
