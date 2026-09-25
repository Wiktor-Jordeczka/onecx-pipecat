"""Agent Configuration adapter: pin a snapshot for a run."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from onecx_pipecat.config import AgentConfigSettings
from onecx_pipecat.models import AgentConfigSnapshot, AgentToolSnapshot


class AgentConfigError(Exception):
    """Raised when an agent/snapshot is not pinned."""


class AgentConfigAdapter(Protocol):
    """Replaceable agent-configuration boundary."""

    async def pin(self, tenant_id: str, agent_id: str) -> AgentConfigSnapshot: ...


@dataclass(frozen=True)
class _Pinned:
    tenant_id: str
    agent_id: str
    version: int
    system_prompt: str
    tool_names: tuple[str, ...]
    tools: tuple[AgentToolSnapshot, ...]

    def snapshot(self) -> AgentConfigSnapshot:
        return AgentConfigSnapshot(
            agent_id=self.agent_id,
            version=self.version,
            system_prompt=self.system_prompt,
            tool_names=list(self.tool_names),
            tools=list(self.tools),
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
        )

    async def pin(self, tenant_id: str, agent_id: str) -> AgentConfigSnapshot:
        candidates = [
            snap for (t, a, _v), snap in self._table.items() if t == tenant_id and a == agent_id
        ]
        if not candidates:
            raise AgentConfigError(f"no pinned snapshot for tenant={tenant_id} agent={agent_id}")
        best = max(candidates, key=lambda s: s.version)
        return best.snapshot()
