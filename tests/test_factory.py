from onecx_pipecat.adapters.factory import (
    build_agent_config,
    build_auth,
    build_chat,
    build_mcp,
    build_permission,
    build_persistence,
    build_service_auth,
    build_stt,
    build_tts,
)
from onecx_pipecat.config import Settings


def test_factory_builds_real_onecx_adapters():
    # OneCX boundaries have no in-memory fallback a deployment could silently run on.
    s = Settings()
    service_auth = build_service_auth(s)
    assert type(service_auth).__name__ == "ClientCredentialsAuth"
    assert type(build_auth(s, service_auth)).__name__ == "JwtAuthAdapter"
    assert type(build_agent_config(s, service_auth)).__name__ == "HttpAgentConfigAdapter"
    assert type(build_chat(s, service_auth)).__name__ == "HttpChatAdapter"
    assert type(build_permission(s, service_auth)).__name__ == "HttpPermissionAdapter"
    assert type(build_mcp(s)).__name__ == "HttpMcpAdapter"


def test_factory_keeps_inmemory_speech_and_persistence():
    # No real speech/persistence adapters exist yet.
    s = Settings()
    assert type(build_stt(s)).__name__ == "InMemorySttAdapter"
    assert type(build_tts(s)).__name__ == "InMemoryTtsAdapter"
    assert type(build_persistence(s)).__name__ == "InMemoryPersistence"
