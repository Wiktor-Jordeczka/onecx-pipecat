"""Composition root: builds adapters from Settings and exposes a summary."""

from __future__ import annotations

from dataclasses import dataclass

from onecx_pipecat.adapters import (
    AgentConfigAdapter,
    AuthAdapter,
    ChatAdapter,
    ConversationPersistence,
    McpAdapter,
    PermissionAdapter,
)
from onecx_pipecat.adapters.factory import (
    build_agent_config,
    build_auth,
    build_chat,
    build_mcp,
    build_permission,
    build_persistence,
    build_service_auth,
)
from onecx_pipecat.config import Settings
from onecx_pipecat.services.credentials import CredentialResolver


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
        service_auth = build_service_auth(self.settings)
        self.auth: AuthAdapter = build_auth(self.settings, service_auth)
        self.agent_config: AgentConfigAdapter = build_agent_config(self.settings, service_auth)
        self.chat: ChatAdapter = build_chat(self.settings, service_auth)
        self.credentials = CredentialResolver(self.settings.credentials)
        self.persistence: ConversationPersistence = build_persistence(self.settings, service_auth)
        self.permission: PermissionAdapter = build_permission(self.settings, service_auth)
        self.mcp: McpAdapter = build_mcp(self.settings)

    def adapters(self) -> AdapterSummary:
        return AdapterSummary(
            auth=_name(self.auth),
            agent_config=_name(self.agent_config),
            chat=_name(self.chat),
            stt=self.settings.speech.stt_provider,
            tts=self.settings.speech.tts_provider,
            persistence=_name(self.persistence),
            permission=_name(self.permission),
            mcp=_name(self.mcp),
        )
