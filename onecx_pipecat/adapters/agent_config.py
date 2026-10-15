"""Agent Configuration adapter: pin a snapshot for a run.

Session start fetches ai-provider ``GET /v1/agents/{id}/configuration`` and
pins the payload for the whole session; changes apply to the next session.
``pin`` fails (``AgentConfigError``) when the agent is missing (``404``),
invalid (``409``), unreachable, or ``voice.voiceEnabled`` is not true — a
voice session must not start without a usable configuration.
"""

from __future__ import annotations

from typing import Any, Protocol

import httpx

from onecx_pipecat.config import AgentConfigSettings
from onecx_pipecat.models import (
    AgentConfigSnapshot,
    McpServerSnapshot,
    PermissionAction,
    ToolRule,
)


class AgentConfigError(Exception):
    """Raised when an agent/snapshot cannot be pinned for a voice session."""


class AgentConfigAdapter(Protocol):
    """Replaceable agent-configuration boundary."""

    async def pin(
        self, tenant_id: str, agent_id: str, apm_principal_token: str
    ) -> AgentConfigSnapshot: ...


class HttpAgentConfigAdapter:
    """Pin the agent configuration from ai-provider ``GET /v1/agents/{id}/configuration``.

    Propagates ``apm-principal-token`` so the configuration is fetched as the
    user. Missing (404), invalid (409), or unreachable agents raise
    ``AgentConfigError``; an agent without ``voice.voiceEnabled`` is rejected
    the same way.
    """

    def __init__(
        self,
        settings: AgentConfigSettings | None = None,
        service_auth: httpx.Auth | None = None,
    ) -> None:
        self._settings = settings or AgentConfigSettings()
        self._service_auth = service_auth
        self._client: httpx.AsyncClient | None = None

    def set_client(self, client: httpx.AsyncClient) -> None:
        """Inject a client (used by tests to avoid a live network call)."""
        self._client = client

    async def pin(
        self, tenant_id: str, agent_id: str, apm_principal_token: str
    ) -> AgentConfigSnapshot:
        client = self._client or httpx.AsyncClient()
        headers = {"apm-principal-token": apm_principal_token}
        try:
            try:
                response = await client.get(
                    f"{self._settings.base_url}/v1/agents/{agent_id}/configuration",
                    headers=headers,
                    auth=self._service_auth,
                )
            except httpx.HTTPError as exc:
                raise AgentConfigError(f"agent configuration unreachable: {exc}") from exc
            if response.status_code == 404:
                raise AgentConfigError(f"no configuration for agent={agent_id}")
            if response.status_code == 409:
                raise AgentConfigError(f"configuration for agent={agent_id} is invalid")
            if not response.is_success:
                raise AgentConfigError(f"agent configuration error: {response.status_code}")
            body: dict[str, Any] = response.json()
            return _parse_configuration(body, agent_id)
        finally:
            if client is not self._client:
                await client.aclose()


def _parse_configuration(body: dict[str, Any], agent_id: str) -> AgentConfigSnapshot:
    """Turn an ``AgentConfiguration`` payload into a snapshot, enforcing voiceEnabled."""
    voice = body.get("voice") or {}
    if voice.get("voiceEnabled") is not True:
        raise AgentConfigError(f"voice disabled for agent={agent_id}")

    try:
        servers = [_parse_mcp_server(entry) for entry in body.get("mcpServers") or []]
    except (KeyError, ValueError) as exc:
        raise AgentConfigError(f"invalid MCP server configuration for agent={agent_id}") from exc

    agent = body.get("agent") or {}
    scaffold = body.get("scaffold") or {}
    return AgentConfigSnapshot(
        agent_id=str(agent.get("id") or agent_id),
        schema_version=str(body.get("schemaVersion", "")),
        system_prompt=str(scaffold.get("systemPrompt") or ""),
        mcp_servers=servers,
    )


def _parse_mcp_server(entry: dict[str, Any]) -> McpServerSnapshot:
    return McpServerSnapshot(
        id=str(entry.get("id") or ""),
        name=str(entry["name"]),
        url=str(entry["url"]),
        credential_ref=str(entry.get("credentialRef") or ""),
        # A server without a resolved unlisted policy advertises nothing it did not list.
        unlisted_tool_permission=PermissionAction(entry.get("unlistedToolPermission") or "DENY"),
        tool_rules=[
            ToolRule(
                tool_name=str(rule["toolName"]),
                permission=PermissionAction(rule["permission"]),
                description=str(rule.get("description") or ""),
            )
            for rule in entry.get("toolRules") or []
        ],
    )
