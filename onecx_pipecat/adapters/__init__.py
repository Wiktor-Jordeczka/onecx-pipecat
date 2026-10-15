"""Replaceable adapter interfaces and in-memory implementations."""

from onecx_pipecat.adapters.agent_config import (
    AgentConfigAdapter,
    HttpAgentConfigAdapter,
    InMemoryAgentConfigAdapter,
)
from onecx_pipecat.adapters.auth import (
    AuthAdapter,
    InMemoryAuthAdapter,
    JwtAuthAdapter,
)
from onecx_pipecat.adapters.chat import (
    ChatAccessError,
    ChatAdapter,
    HttpChatAdapter,
    InMemoryChatAdapter,
)
from onecx_pipecat.adapters.mcp import (
    HttpMcpAdapter,
    InMemoryMcpAdapter,
    McpAdapter,
    McpDiscovery,
    McpToolResult,
)
from onecx_pipecat.adapters.permission import InMemoryPermissionAdapter, PermissionAdapter
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
    "InMemoryAgentConfigAdapter",
    "InMemoryAuthAdapter",
    "InMemoryChatAdapter",
    "InMemoryMcpAdapter",
    "InMemoryPermissionAdapter",
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
