"""MCP adapter: invoke a tool and surface the structured result.

Also discovers the session's tool surface once per session (``discover``): it
queries each configured MCP server a single time, propagating the
``apm-principal-token``, and reports — rather than raises — any server that
fails, so the session continues in a degraded state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx

from onecx_pipecat.config import McpSettings
from onecx_pipecat.models import AgentToolSnapshot, ToolProposal


@dataclass
class McpToolResult:
    """Structured result of a tool invocation (success or sanitized failure)."""

    ok: bool
    value: Any = None
    error: str = ""


@dataclass
class McpDiscovery:
    """The result of a one-time tool discovery across configured servers.

    ``degraded`` is a list of ``(server_name, reason)`` pairs: one entry per
    server that failed, so the session can emit a degraded-capability event
    and continue with the tools it was able to resolve.
    """

    tools: list[AgentToolSnapshot] = field(default_factory=list)
    degraded: list[tuple[str, str]] = field(default_factory=list)


class McpAdapter(Protocol):
    async def invoke(
        self, proposal: ToolProposal, args: dict[str, Any] | None = None
    ) -> McpToolResult: ...

    async def discover(self, apm_principal_token: str) -> McpDiscovery:
        """Discover tools once, across every configured server, skipping failures."""
        ...


class InMemoryMcpAdapter:
    """Deterministic table of tool handlers; unknown tools are a sanitized failure.

    The failure shape mirrors the ``MCP_FAILURE`` branch in the prototype:
    ``ok=False`` plus a stable ``error`` string the assistant can reason over.
    ``discover`` returns the registered tools and reports any server marked
    (or seeded to) fail, so degraded-capability behavior is testable offline.
    """

    def __init__(self, settings: McpSettings | None = None) -> None:
        self._settings = settings or McpSettings()
        self._handlers_by_server: dict[str, dict[str, Any]] = {}
        self._failures_by_server: dict[str, str] = {}

    def register(self, tool_name: str, handler: Any, server_name: str | None = None) -> None:
        target_server = server_name or self._settings.default_server_name
        if target_server not in self._settings.servers:
            raise ValueError(f"unknown MCP server {target_server!r}")
        self._handlers_by_server.setdefault(target_server, {})[tool_name] = handler

    def mark_degraded(self, server_name: str, reason: str) -> None:
        """Record that a server failed discovery (test-only; no live network)."""
        self._failures_by_server[server_name] = reason

    async def discover(self, apm_principal_token: str) -> McpDiscovery:
        """Query each configured server once, propagating the principal token.

        A server with no registered tools and no recorded failure is healthy
        but empty; a recorded failure is skipped and reported instead of
        raising.
        """
        discovery = McpDiscovery()
        for server_name in self._settings.servers:
            reason = self._failures_by_server.get(server_name)
            if reason is not None:
                discovery.degraded.append((server_name, reason))
                continue
            for tool_name in self._handlers_by_server.get(server_name, {}):
                discovery.tools.append(
                    AgentToolSnapshot(tool_name=tool_name, server_name=server_name)
                )
        return discovery

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


class HttpMcpAdapter:
    """Discover tools over HTTP MCP servers, skipping and reporting failures.

    A real deployment calls each server's ``tools/list`` with the principal
    token and applies ``mcp.timeout_seconds``; a server error is captured as a
    degraded entry so discovery of the remaining servers still completes.
    """

    def __init__(self, settings: McpSettings | None = None) -> None:
        self._settings = settings or McpSettings()
        self._client: httpx.AsyncClient | None = None

    def set_client(self, client: httpx.AsyncClient) -> None:
        """Inject a client (used by tests to avoid a live network call)."""
        self._client = client

    async def discover(self, apm_principal_token: str) -> McpDiscovery:
        discovery = McpDiscovery()
        client = self._client or httpx.AsyncClient(timeout=self._settings.timeout_seconds)
        headers = {"apm-principal-token": apm_principal_token}
        try:
            for server_name, server_url in self._settings.servers.items():
                if not str(server_url).startswith("http"):
                    # Non-HTTP (in-memory) servers are not discoverable over HTTP.
                    continue
                try:
                    response = await client.post(
                        f"{server_url.rstrip('/')}/tools/list",
                        headers=headers,
                        json={},
                    )
                    if not response.is_success:
                        discovery.degraded.append((server_name, f"HTTP {response.status_code}"))
                        continue
                    for entry in response.json().get("tools", []):
                        discovery.tools.append(
                            AgentToolSnapshot(
                                tool_id=str(entry.get("id", "")),
                                tool_name=str(entry.get("name", "")),
                                tool_description=str(entry.get("description", "")),
                                server_name=server_name,
                                server_url=str(server_url),
                            )
                        )
                except httpx.HTTPError as exc:
                    discovery.degraded.append((server_name, str(exc)))
        finally:
            if self._client is None:
                await client.aclose()
        return discovery

    async def invoke(
        self, proposal: ToolProposal, args: dict[str, Any] | None = None
    ) -> McpToolResult:
        return McpToolResult(ok=False, error="HttpMcpAdapter is discovery-only in this foundation")
