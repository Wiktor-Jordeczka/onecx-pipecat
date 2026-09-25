import base64

import pytest
from fastapi.testclient import TestClient
from fastapi.websockets import WebSocketDisconnect

from onecx_pipecat.app import create_app
from onecx_pipecat.config import Settings
from onecx_pipecat.container import AppContainer

_AUDIO = base64.b64encode(b"pcm").decode("ascii")


def _container() -> AppContainer:
    container = AppContainer(Settings())
    container.auth.seed("t-1", subject="user-1", tenant_id="local", roles=["voice"])
    container.agent_config.register("local", "onecx-agent", 1, system_prompt="be brief")
    return container


def test_ws_rejects_missing_token():
    client = TestClient(create_app(_container()))
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws/voice") as ws:
            ws.receive_json()


def test_ws_rejects_unknown_token():
    client = TestClient(create_app(_container()))
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws/voice?token=nope") as ws:
            ws.receive_json()


def test_ws_voice_turn_happy_path():
    client = TestClient(create_app(_container()))
    with client.websocket_connect("/ws/voice?token=t-1") as ws:
        ws.send_json({"type": "start_session", "agent_id": "onecx-agent"})
        ready = ws.receive_json()
        assert ready["kind"] == "session_ready"
        assert ready["agent_version"] == 1

        ws.send_json({"type": "audio", "audio": _AUDIO})
        assert ws.receive_json()["kind"] == "transcript"
        assert ws.receive_json()["kind"] == "assistant_text"
        assert ws.receive_json()["kind"] == "assistant_audio"
        assert ws.receive_json()["kind"] == "turn_complete"

        ws.send_json({"type": "stop"})
        assert ws.receive_json()["kind"] == "session_closed"


def test_ws_audio_before_start_reports_illegal_state():
    client = TestClient(create_app(_container()))
    with client.websocket_connect("/ws/voice?token=t-1") as ws:
        ws.send_json({"type": "audio", "audio": _AUDIO})
        event = ws.receive_json()
        assert event["kind"] == "error"
        assert event["code"] == "illegal_state"


def test_ws_malformed_command_is_rejected():
    client = TestClient(create_app(_container()))
    with client.websocket_connect("/ws/voice?token=t-1") as ws:
        ws.send_json({"type": "nonsense"})
        event = ws.receive_json()
        assert event["kind"] == "error"
        assert event["code"] == "bad_command"
