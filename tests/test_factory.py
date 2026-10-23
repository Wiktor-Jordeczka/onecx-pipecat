from onecx_pipecat.adapters.factory import (
    build_agent_config,
    build_auth,
    build_chat,
    build_mcp,
    build_permission,
    build_persistence,
    build_service_auth,
)
from onecx_pipecat.config import PersistenceSettings, Settings


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


def test_factory_selects_persistence_backend():
    assert type(build_persistence(Settings())).__name__ == "HttpChatPersistence"
    s = Settings(persistence=PersistenceSettings(backend="inmemory"))
    assert type(build_persistence(s)).__name__ == "InMemoryPersistence"
