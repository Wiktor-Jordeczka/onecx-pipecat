"""Permission adapter: evaluate a tool call and drive decisions."""

from __future__ import annotations

from typing import Protocol

from onecx_pipecat.config import PermissionSettings
from onecx_pipecat.models import PermissionAction, PermissionDecision, ToolProposal


class PermissionAdapter(Protocol):
    async def evaluate(self, proposal: ToolProposal) -> PermissionDecision: ...


class InMemoryPermissionAdapter:
    """Policy: any tool whose name starts with the write prefix is ALWAYS_ASK,
    everything else falls back to the configured ``default_action``. Matches
    the ``ALWAYS_ASK`` flow in the prototype while honoring the documented
    ``permission.default_action`` fallback."""

    def __init__(self, settings: PermissionSettings | None = None) -> None:
        self._settings = settings or PermissionSettings()
        self._write_prefix = ("write_", "delete_", "send_")

    async def evaluate(self, proposal: ToolProposal) -> PermissionDecision:
        if any(proposal.tool_name.startswith(p) for p in self._write_prefix):
            return PermissionDecision(
                action=PermissionAction.ALWAYS_ASK,
                reason=f"tool {proposal.tool_name!r} requires approval",
            )
        # The configured default is the operator's documented choice for tools
        # that match no explicit policy; it is case-insensitive (config values
        # are lowercase, ``PermissionAction`` values are uppercase).
        default_action = PermissionAction(self._settings.default_action.strip().upper())
        return PermissionDecision(action=default_action, reason="default policy")
