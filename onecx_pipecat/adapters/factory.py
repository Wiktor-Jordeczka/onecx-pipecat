"""Concrete adapter construction from Settings.

Every function takes Settings and returns the implementation selected by that
capability's ``backend`` setting. Capabilities that ship an HTTP/real
implementation (agent configuration, chat access, MCP) default to the
in-memory stand-in and select the real adapter purely by configuration, so a
deployment switches them without a code change. Swapping a capability for an
adapter that does not yet exist means writing a new module and changing exactly
one of these call sites.
"""

from __future__ import annotations

from onecx_pipecat.adapters.agent_config import (
    HttpAgentConfigAdapter,
    InMemoryAgentConfigAdapter,
)
from onecx_pipecat.adapters.auth import InMemoryAuthAdapter
from onecx_pipecat.adapters.chat import HttpChatAdapter, InMemoryChatAdapter
from onecx_pipecat.adapters.mcp import HttpMcpAdapter, InMemoryMcpAdapter
from onecx_pipecat.adapters.permission import InMemoryPermissionAdapter
from onecx_pipecat.adapters.persistence import InMemoryPersistence
from onecx_pipecat.adapters.speech import InMemorySttAdapter, InMemoryTtsAdapter
from onecx_pipecat.config import Settings


def build_auth(settings: Settings):
    return InMemoryAuthAdapter(settings.auth)


def build_agent_config(settings: Settings):
    if settings.agent_config.backend == "http":
        return HttpAgentConfigAdapter(settings.agent_config)
    return InMemoryAgentConfigAdapter(settings.agent_config)


def build_chat(settings: Settings):
    if settings.chat.backend == "http":
        return HttpChatAdapter(settings.chat)
    return InMemoryChatAdapter(settings.chat)


def build_stt(settings: Settings):
    return InMemorySttAdapter(settings.speech)


def build_tts(settings: Settings):
    return InMemoryTtsAdapter(settings.speech)


def build_persistence(settings: Settings):
    return InMemoryPersistence(settings.persistence)


def build_permission(settings: Settings):
    return InMemoryPermissionAdapter(settings.permission)


def build_mcp(settings: Settings):
    if settings.mcp.backend == "http":
        return HttpMcpAdapter(settings.mcp)
    return InMemoryMcpAdapter(settings.mcp)
