from onecx_pipecat.config import Settings
from onecx_pipecat.container import AppContainer


def test_container_binds_real_onecx_adapters():
    s = AppContainer(Settings()).adapters()
    assert s.auth == "JwtAuthAdapter"
    assert s.agent_config == "HttpAgentConfigAdapter"
    assert s.chat == "HttpChatAdapter"
    assert s.stt == "inmemory"
    assert s.tts == "inmemory"
    assert s.persistence == "HttpChatPersistence"
    assert s.permission == "HttpPermissionAdapter"
    assert s.mcp == "HttpMcpAdapter"


def test_container_isolates_adapters_between_instances():
    a = AppContainer(Settings())
    b = AppContainer(Settings())
    assert a.persistence is not b.persistence
    assert a.mcp is not b.mcp
