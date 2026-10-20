"""Concrete adapter construction from Settings.

OneCX boundaries (auth, agent configuration, chat, permission, MCP) always use
their real implementation; there is no in-memory fallback that a deployment
could silently run on. Speech services are built per session in
``onecx_pipecat.services.speech``. Persistence is onecx-chat-svc by default;
`inmemory` is for tests and local runs.
"""

from __future__ import annotations

from onecx_pipecat.adapters.agent_config import HttpAgentConfigAdapter
from onecx_pipecat.adapters.auth import ClientCredentialsAuth, JwtAuthAdapter
from onecx_pipecat.adapters.chat import HttpChatAdapter
from onecx_pipecat.adapters.mcp import HttpMcpAdapter
from onecx_pipecat.adapters.permission import HttpPermissionAdapter
from onecx_pipecat.adapters.persistence import HttpChatPersistence, InMemoryPersistence
from onecx_pipecat.config import Settings


def build_service_auth(settings: Settings) -> ClientCredentialsAuth:
    return ClientCredentialsAuth(settings.auth)


def build_auth(settings: Settings, service_auth: ClientCredentialsAuth):
    return JwtAuthAdapter(settings.auth, service_auth)


def build_agent_config(settings: Settings, service_auth: ClientCredentialsAuth):
    return HttpAgentConfigAdapter(settings.agent_config, service_auth)


def build_chat(settings: Settings, service_auth: ClientCredentialsAuth):
    return HttpChatAdapter(settings.chat, service_auth)


def build_persistence(settings: Settings, service_auth: ClientCredentialsAuth | None = None):
    if settings.persistence.backend == "inmemory":
        return InMemoryPersistence(settings.persistence)
    return HttpChatPersistence(settings.chat, service_auth)


def build_permission(settings: Settings, service_auth: ClientCredentialsAuth):
    return HttpPermissionAdapter(settings.permission, service_auth)


def build_mcp(settings: Settings):
    # MCP servers are per-agent and may be external: Pipecat's service token is not sent there.
    return HttpMcpAdapter(settings.mcp)
