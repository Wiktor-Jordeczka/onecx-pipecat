"""Agent Configuration adapter: pin a snapshot for a run.

Session start fetches ``GET /v1/agents/{agent_id}/configuration`` and pins the
payload for the whole session; changes apply to the next session. ``pin``
fails (``AgentConfigError``) when the agent is missing/invalid (``409``),
unreachable, or ``voice.enabled`` is false — a voice session must not start
without a usable configuration.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from onecx_pipecat.config import AgentConfigSettings
from onecx_pipecat.models import (
    AgentConfigSnapshot,
    AgentToolSnapshot,
    ExecutionPolicy,
    PermissionAction,
)


class AgentConfigError(Exception):
    """Raised when an agent/snapshot cannot be pinned for a voice session."""


class AgentConfigAdapter(Protocol):
    """Replaceable agent-configuration boundary."""

    async def pin(
        self, tenant_id: str, agent_id: str, apm_principal_token: str
    ) -> AgentConfigSnapshot: ...


@dataclass(frozen=True)
class _Pinned:
    tenant_id: str
    agent_id: str
    version: int
    system_prompt: str
    tool_names: tuple[str, ...]
    tools: tuple[AgentToolSnapshot, ...]
    unlisted_tool_permission: PermissionAction
    voice_enabled: bool

    def snapshot(self) -> AgentConfigSnapshot:
        return AgentConfigSnapshot(
            agent_id=self.agent_id,
            version=self.version,
            system_prompt=self.system_prompt,
            tool_names=list(self.tool_names),
            tools=list(self.tools),
            unlisted_tool_permission=self.unlisted_tool_permission,
            voice_enabled=self.voice_enabled,
        )


class InMemoryAgentConfigAdapter:
    def __init__(self, settings: AgentConfigSettings | None = None) -> None:
        self._settings = settings or AgentConfigSettings()
        self._table: dict[tuple[str, str, int], _Pinned] = {}

    def register(
        self,
        tenant_id: str,
        agent_id: str,
        version: int,
        system_prompt: str = "",
        tool_names: list[str] | None = None,
        tools: list[AgentToolSnapshot] | None = None,
        *,
        unlisted_tool_permission: PermissionAction = PermissionAction.ALWAYS_ASK,
        voice_enabled: bool = True,
    ) -> None:
        pinned_tools = tuple(tools or ())
        # Backward compatibility: existing callers provide only tool_names.
        if tool_names is None:
            names = tuple(t.tool_name for t in pinned_tools)
        else:
            names = tuple(tool_names)
        self._table[(tenant_id, agent_id, version)] = _Pinned(
            tenant_id=tenant_id,
            agent_id=agent_id,
            version=version,
            system_prompt=system_prompt,
            tool_names=names,
            tools=pinned_tools,
            unlisted_tool_permission=unlisted_tool_permission,
            voice_enabled=voice_enabled,
        )

    async def pin(
        self, tenant_id: str, agent_id: str, apm_principal_token: str
    ) -> AgentConfigSnapshot:
        candidates = [
            snap for (t, a, _v), snap in self._table.items() if t == tenant_id and a == agent_id
        ]
        if not candidates:
            raise AgentConfigError(f"no pinned snapshot for tenant={tenant_id} agent={agent_id}")
        best = max(candidates, key=lambda s: s.version)
        if not best.voice_enabled:
            raise AgentConfigError(f"voice disabled for tenant={tenant_id} agent={agent_id}")
        return best.snapshot()


class HttpAgentConfigAdapter:
    """Pin the agent configuration from ``GET /v1/agents/{agent_id}/configuration``.

    Propagates ``apm-principal-token`` so the configuration is fetched as the
    user. Missing (404), invalid (409), or unreachable agents raise
    ``AgentConfigError``; ``voice.enabled`` false is rejected the same way.
    """

    def __init__(self, settings: AgentConfigSettings | None = None) -> None:
        self._settings = settings or AgentConfigSettings()
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
            response = await client.get(
                f"{self._settings.base_url}/v1/agents/{agent_id}/configuration", headers=headers
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
        snapshot = _parse_configuration(body, agent_id)
        if client is not self._client:
            await client.aclose()
        return snapshot


def _parse_configuration(body: dict[str, Any], agent_id: str) -> AgentConfigSnapshot:
    """Turn the configuration payload into a snapshot, enforcing voice.enabled."""
    voice = body.get("voice")
    if isinstance(voice, dict) and voice.get("enabled") is False:
        raise AgentConfigError(f"voice disabled for agent={agent_id}")

    tools: list[AgentToolSnapshot] = []
    for entry in body.get("tools", []):
        tools.append(
            AgentToolSnapshot(
                tool_id=str(entry.get("toolId", entry.get("tool_id", ""))),
                tool_name=str(entry.get("name", entry.get("tool_name", ""))),
                tool_description=str(entry.get("description", "")),
                server_name=str(entry.get("serverName", entry.get("server_name", "inmemory"))),
                server_url=str(entry.get("serverUrl", entry.get("server_url", "inmemory"))),
                execution_policy=ExecutionPolicy(entry.get("executionPolicy", "ALWAYS_ASK")),
            )
        )

    unlisted_raw = body.get("unlistedToolPermission", "ALWAYS_ASK")
    return AgentConfigSnapshot(
        agent_id=agent_id,
        version=int(body.get("version", 1)),
        system_prompt=str(body.get("systemPrompt", body.get("system_prompt", ""))),
        tool_names=[t.tool_name for t in tools],
        tools=tools,
        unlisted_tool_permission=PermissionAction(unlisted_raw),
        voice_enabled=True,
    )
