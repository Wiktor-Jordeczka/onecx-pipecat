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


def test_factory_builds_inmemory_adapters_by_default():
    s = Settings()
    assert type(build_auth(s)).__name__ == "InMemoryAuthAdapter"
    assert type(build_agent_config(s)).__name__ == "InMemoryAgentConfigAdapter"
    assert type(build_chat(s)).__name__ == "InMemoryChatAdapter"
    assert type(build_stt(s)).__name__ == "InMemorySttAdapter"
    assert type(build_tts(s)).__name__ == "InMemoryTtsAdapter"
    assert type(build_persistence(s)).__name__ == "InMemoryPersistence"
    assert type(build_permission(s)).__name__ == "InMemoryPermissionAdapter"
    assert type(build_mcp(s)).__name__ == "InMemoryMcpAdapter"
