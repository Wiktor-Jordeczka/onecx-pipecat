"""Concrete adapter construction from Settings.

Every function takes Settings and returns an in-memory implementation.
Swapping a capability for a real adapter means writing a new module and
changing exactly one of these call sites.
"""

from __future__ import annotations

from onecx_pipecat.adapters.agent_config import InMemoryAgentConfigAdapter
from onecx_pipecat.adapters.auth import InMemoryAuthAdapter
from onecx_pipecat.adapters.chat import InMemoryChatAdapter
from onecx_pipecat.adapters.mcp import InMemoryMcpAdapter
from onecx_pipecat.adapters.permission import InMemoryPermissionAdapter
from onecx_pipecat.adapters.persistence import InMemoryPersistence
from onecx_pipecat.adapters.speech import InMemorySttAdapter, InMemoryTtsAdapter
from onecx_pipecat.config import Settings


def build_auth(settings: Settings):
    return InMemoryAuthAdapter(settings.auth)


def build_agent_config(settings: Settings):
    return InMemoryAgentConfigAdapter(settings.agent_config)


def build_chat(settings: Settings):
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
    return InMemoryMcpAdapter(settings.mcp)
