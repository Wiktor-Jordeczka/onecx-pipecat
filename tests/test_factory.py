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


def test_factory_selects_http_adapters_by_configuration():
    # Selecting a real (HTTP) adapter is a configuration change, not a code
    # change: the same build_* functions return the exported Http implementations.
    s = Settings(
        agent_config={"backend": "http"},
        chat={"backend": "http"},
        mcp={"backend": "http"},
    )
    assert type(build_agent_config(s)).__name__ == "HttpAgentConfigAdapter"
    assert type(build_chat(s)).__name__ == "HttpChatAdapter"
    assert type(build_mcp(s)).__name__ == "HttpMcpAdapter"
    # Capabilities with no HTTP implementation still return the in-memory one.
    assert type(build_auth(s)).__name__ == "InMemoryAuthAdapter"
    assert type(build_permission(s)).__name__ == "InMemoryPermissionAdapter"


def test_factory_backend_defaults_are_inmemory():
    s = Settings()
    assert s.agent_config.backend == "inmemory"
    assert s.chat.backend == "inmemory"
    assert s.mcp.backend == "inmemory"


def test_factory_backend_env_override(monkeypatch):
    # The backend selector is a plain nested setting, so the environment
    # overrides it the way every other adapter knob does.
    monkeypatch.setenv("ONECX_CHAT__BACKEND", "http")
    s = Settings(_env_file=None)
    assert type(build_chat(s)).__name__ == "HttpChatAdapter"
