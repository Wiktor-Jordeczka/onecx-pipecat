"""MCP adapter: invoke a tool and surface the structured result."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from onecx_pipecat.config import McpSettings
from onecx_pipecat.models import ToolProposal


@dataclass
class McpToolResult:
    """Structured result of a tool invocation (success or sanitized failure)."""

    ok: bool
    value: Any = None
    error: str = ""


class McpAdapter(Protocol):
    async def invoke(
        self, proposal: ToolProposal, args: dict[str, Any] | None = None
    ) -> McpToolResult: ...


class InMemoryMcpAdapter:
    """Deterministic table of tool handlers; unknown tools are a sanitized failure.

    The failure shape mirrors the ``MCP_FAILURE`` branch in the prototype:
    ``ok=False`` plus a stable ``error`` string the assistant can reason over.
    """

    def __init__(self, settings: McpSettings | None = None) -> None:
        self._settings = settings or McpSettings()
        self._handlers_by_server: dict[str, dict[str, Any]] = {}

    def register(self, tool_name: str, handler: Any, server_name: str | None = None) -> None:
        target_server = server_name or self._settings.default_server_name
        if target_server not in self._settings.servers:
            raise ValueError(f"unknown MCP server {target_server!r}")
        self._handlers_by_server.setdefault(target_server, {})[tool_name] = handler

    async def invoke(
        self, proposal: ToolProposal, args: dict[str, Any] | None = None
    ) -> McpToolResult:
        target_server = proposal.server_name or self._settings.default_server_name
        if target_server not in self._settings.servers:
            return McpToolResult(ok=False, error=f"unknown MCP server {target_server!r}")

        handler = self._handlers_by_server.get(target_server, {}).get(proposal.tool_name)
        if handler is None:
            return McpToolResult(
                ok=False,
                error=f"unknown tool {proposal.tool_name!r} on server {target_server!r}",
            )
        try:
            value = await handler(dict(args if args is not None else proposal.arguments))
        except Exception as exc:  # noqa: BLE001 - sanitized boundary
            return McpToolResult(ok=False, error=f"{type(exc).__name__}: {exc}")
        return McpToolResult(ok=True, value=value)
