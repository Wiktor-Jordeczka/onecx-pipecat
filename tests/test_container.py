import pytest

from onecx_pipecat.adapters.auth import AuthenticationError
from onecx_pipecat.config import Settings
from onecx_pipecat.container import AppContainer


def test_container_binds_inmemory_adapters_by_default():
    c = AppContainer(Settings())
    s = c.adapters()
    assert s.auth == "InMemoryAuthAdapter"
    assert s.agent_config == "InMemoryAgentConfigAdapter"
    assert s.chat == "InMemoryChatAdapter"
    assert s.stt == "InMemorySttAdapter"
    assert s.tts == "InMemoryTtsAdapter"
    assert s.persistence == "InMemoryPersistence"
    assert s.permission == "InMemoryPermissionAdapter"
    assert s.mcp == "InMemoryMcpAdapter"


async def test_container_isolate_adapters_between_instances():
    a = AppContainer(Settings())
    b = AppContainer(Settings())
    a.auth.seed("tok", "u", "t")
    with pytest.raises(AuthenticationError):
        await b.auth.authenticate("tok")
