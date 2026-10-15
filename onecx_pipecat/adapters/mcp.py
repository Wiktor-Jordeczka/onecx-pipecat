"""MCP adapter: invoke a tool and surface the structured result.

Also discovers the session's tool surface once per session (``discover``): it
queries each MCP server of the pinned agent configuration a single time,
propagating the ``apm-principal-token``, and reports — rather than raises —
any server that fails, so the session continues in a degraded state.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.types import TextContent

from onecx_pipecat.config import McpSettings
from onecx_pipecat.models import AgentToolSnapshot, McpServerSnapshot, ToolProposal


@dataclass
class McpToolResult:
    """Structured result of a tool invocation (success or sanitized failure)."""

    ok: bool
    value: Any = None
    error: str = ""


@dataclass
class McpDiscovery:
    """The result of a one-time tool discovery across the agent's servers.

    ``degraded`` is a list of ``(server_name, reason)`` pairs: one entry per
    server that failed, so the session can emit a degraded-capability event
    and continue with the tools it was able to resolve.
    """

    tools: list[AgentToolSnapshot] = field(default_factory=list)
    degraded: list[tuple[str, str]] = field(default_factory=list)


class McpAdapter(Protocol):
    async def invoke(
        self,
        server: McpServerSnapshot,
        proposal: ToolProposal,
        apm_principal_token: str,
        args: dict[str, Any] | None = None,
    ) -> McpToolResult: ...

    async def discover(
        self, servers: list[McpServerSnapshot], apm_principal_token: str
    ) -> McpDiscovery:
        """Discover tools once, across the given servers, skipping failures."""
        ...


class HttpMcpAdapter:
    """Talk to the agent's MCP servers over MCP Streamable HTTP (official ``mcp`` SDK).

    Each call opens a session (``initialize``), propagating the principal token
    and applying ``mcp.timeout_seconds``. A server that fails discovery is
    captured as a degraded entry so the remaining servers still complete.
    """

    def __init__(self, settings: McpSettings | None = None) -> None:
        self._settings = settings or McpSettings()
        self._transport: httpx.AsyncBaseTransport | None = None

    def set_transport(self, transport: httpx.AsyncBaseTransport) -> None:
        """Inject an HTTP transport (tests run an in-process MCP server)."""
        self._transport = transport

    @asynccontextmanager
    async def _session(
        self, server: McpServerSnapshot, apm_principal_token: str
    ) -> AsyncIterator[ClientSession]:
        async with httpx.AsyncClient(
            headers={"apm-principal-token": apm_principal_token},
            timeout=self._settings.timeout_seconds,
            follow_redirects=True,
            transport=self._transport,
        ) as http_client:
            async with streamable_http_client(server.url, http_client=http_client) as (
                read,
                write,
                _,
            ):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    yield session

    async def discover(
        self, servers: list[McpServerSnapshot], apm_principal_token: str
    ) -> McpDiscovery:
        discovery = McpDiscovery()
        for server in servers:
            try:
                tools = await self._list_tools(server, apm_principal_token)
            except Exception as exc:  # noqa: BLE001 - any server failure degrades, never aborts
                discovery.degraded.append((server.name, _reason(exc)))
                continue
            discovery.tools.extend(tools)
        return discovery

    async def _list_tools(
        self, server: McpServerSnapshot, apm_principal_token: str
    ) -> list[AgentToolSnapshot]:
        tools: list[AgentToolSnapshot] = []
        async with self._session(server, apm_principal_token) as session:
            cursor: str | None = None
            while True:
                page = await session.list_tools(cursor)
                tools.extend(
                    AgentToolSnapshot(
                        tool_name=tool.name,
                        tool_description=tool.description or "",
                        server_name=server.name,
                        server_url=server.url,
                    )
                    for tool in page.tools
                )
                cursor = page.nextCursor
                if not cursor:
                    return tools

    async def invoke(
        self,
        server: McpServerSnapshot,
        proposal: ToolProposal,
        apm_principal_token: str,
        args: dict[str, Any] | None = None,
    ) -> McpToolResult:
        arguments = dict(args if args is not None else proposal.arguments)
        try:
            async with self._session(server, apm_principal_token) as session:
                result = await session.call_tool(proposal.tool_name, arguments)
        except Exception as exc:  # noqa: BLE001 - sanitized boundary
            return McpToolResult(ok=False, error=_reason(exc))
        text = "\n".join(c.text for c in result.content if isinstance(c, TextContent))
        if result.isError:
            return McpToolResult(ok=False, error=text or "tool reported an error")
        value = result.structuredContent if result.structuredContent is not None else text
        return McpToolResult(ok=True, value=value)


def _reason(exc: BaseException) -> str:
    """The innermost cause, unwrapped from the SDK's task-group exception groups."""
    while isinstance(exc, BaseExceptionGroup) and exc.exceptions:
        exc = exc.exceptions[0]
    return f"{type(exc).__name__}: {exc}"
