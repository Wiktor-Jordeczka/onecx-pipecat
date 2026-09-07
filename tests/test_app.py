from httpx import ASGITransport, AsyncClient

from onecx_pipecat.app import create_app
from onecx_pipecat.config import Settings
from onecx_pipecat.container import AppContainer


async def test_healthz_returns_ok_with_adapter_summary():
    app = create_app(AppContainer(Settings()))
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/healthz")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "OK"
    assert body["app"] == "onecx-pipecat"
    assert body["adapters"]["stt"] == "InMemorySttAdapter"
    assert body["adapters"]["permission"] == "InMemoryPermissionAdapter"
    assert body["adapters"]["mcp"] == "InMemoryMcpAdapter"
    assert body["pipecat_version"]


async def test_app_rejects_unknown_path():
    app = create_app(AppContainer(Settings()))
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/does-not-exist")
    assert resp.status_code == 404
