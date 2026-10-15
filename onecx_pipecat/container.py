"""Composition root: builds adapters from Settings and exposes a summary."""

from __future__ import annotations

from dataclasses import dataclass

from onecx_pipecat.adapters import (
    AgentConfigAdapter,
    AuthAdapter,
    ChatAdapter,
    InMemoryPersistence,
    McpAdapter,
    PermissionAdapter,
    SttAdapter,
    TtsAdapter,
)
from onecx_pipecat.adapters.factory import (
    build_agent_config,
    build_auth,
    build_chat,
    build_mcp,
    build_permission,
    build_persistence,
    build_stt,
    build_tts,
)
from onecx_pipecat.config import Settings


@dataclass(frozen=True)
class AdapterSummary:
    auth: str
    agent_config: str
    chat: str
    stt: str
    tts: str
    persistence: str
    permission: str
    mcp: str


def _name(obj) -> str:
    return obj.__class__.__name__


class AppContainer:
    """Owns the concrete adapter instances for one app lifetime."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or Settings()
        self.auth: AuthAdapter = build_auth(self.settings)
        self.agent_config: AgentConfigAdapter = build_agent_config(self.settings)
        self.chat: ChatAdapter = build_chat(self.settings)
        self.stt: SttAdapter = build_stt(self.settings)
        self.tts: TtsAdapter = build_tts(self.settings)
        self.persistence: InMemoryPersistence = build_persistence(self.settings)
        self.permission: PermissionAdapter = build_permission(self.settings)
        self.mcp: McpAdapter = build_mcp(self.settings)

    def adapters(self) -> AdapterSummary:
        return AdapterSummary(
            auth=_name(self.auth),
            agent_config=_name(self.agent_config),
            chat=_name(self.chat),
            stt=_name(self.stt),
            tts=_name(self.tts),
            persistence=_name(self.persistence),
            permission=_name(self.permission),
            mcp=_name(self.mcp),
        )
