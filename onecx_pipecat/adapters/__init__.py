"""Replaceable adapter interfaces and their implementations."""

from onecx_pipecat.adapters.agent_config import AgentConfigAdapter, HttpAgentConfigAdapter
from onecx_pipecat.adapters.auth import AuthAdapter, JwtAuthAdapter
from onecx_pipecat.adapters.chat import ChatAccessError, ChatAdapter, HttpChatAdapter
from onecx_pipecat.adapters.mcp import (
    HttpMcpAdapter,
    McpAdapter,
    McpDiscovery,
    McpToolResult,
)
from onecx_pipecat.adapters.permission import HttpPermissionAdapter, PermissionAdapter
from onecx_pipecat.adapters.persistence import ConversationPersistence, InMemoryPersistence
from onecx_pipecat.adapters.speech import (
    InMemorySttAdapter,
    InMemoryTtsAdapter,
    SttAdapter,
    TtsAdapter,
)

__all__ = [
    "AgentConfigAdapter",
    "AuthAdapter",
    "ChatAdapter",
    "ChatAccessError",
    "ConversationPersistence",
    "HttpAgentConfigAdapter",
    "HttpChatAdapter",
    "HttpMcpAdapter",
    "HttpPermissionAdapter",
    "InMemoryPersistence",
    "InMemorySttAdapter",
    "InMemoryTtsAdapter",
    "JwtAuthAdapter",
    "McpAdapter",
    "McpDiscovery",
    "McpToolResult",
    "PermissionAdapter",
    "SttAdapter",
    "TtsAdapter",
]
