"""Replaceable adapter interfaces and in-memory implementations."""

from onecx_pipecat.adapters.agent_config import (
    AgentConfigAdapter,
    InMemoryAgentConfigAdapter,
)
from onecx_pipecat.adapters.auth import AuthAdapter, InMemoryAuthAdapter
from onecx_pipecat.adapters.mcp import InMemoryMcpAdapter, McpAdapter, McpToolResult
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
    "ConversationPersistence",
    "InMemoryAgentConfigAdapter",
    "InMemoryAuthAdapter",
    "InMemoryMcpAdapter",
    "InMemoryPermissionAdapter",
    "InMemoryPersistence",
    "InMemorySttAdapter",
    "InMemoryTtsAdapter",
    "McpAdapter",
    "McpToolResult",
    "PermissionAdapter",
    "SttAdapter",
    "TtsAdapter",
]
