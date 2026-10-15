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
    container.chat.register("chat-1", title="general")
    container.agent_config.register("local", "onecx-agent", 1, system_prompt="be brief")
    return container


def _start(token: str = "t-1") -> dict:
    return {
        "type": "start_session",
        "agent_id": "onecx-agent",
        "chat_id": "chat-1",
        "apm_principal_token": token,
    }


def test_ws_rejects_token_in_url():
    client = TestClient(create_app(_container()))
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws/voice?token=t-1") as ws:
            ws.receive_json()


def test_ws_start_session_with_invalid_token_reports_error():
    client = TestClient(create_app(_container()))
    with client.websocket_connect("/ws/voice") as ws:
        ws.send_json(_start(token="nope"))
        event = ws.receive_json()
        assert event["kind"] == "error"
        assert event["code"] == "authentication_failed"


def test_ws_voice_turn_happy_path():
    client = TestClient(create_app(_container()))
    with client.websocket_connect("/ws/voice") as ws:
        ws.send_json(_start())
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
    with client.websocket_connect("/ws/voice") as ws:
        ws.send_json({"type": "audio", "audio": _AUDIO})
        event = ws.receive_json()
        assert event["kind"] == "error"
        assert event["code"] == "illegal_state"


def test_ws_malformed_command_is_rejected():
    client = TestClient(create_app(_container()))
    with client.websocket_connect("/ws/voice") as ws:
        ws.send_json({"type": "nonsense"})
        event = ws.receive_json()
        assert event["kind"] == "error"
        assert event["code"] == "bad_command"


def test_ws_refresh_token_updates_tokens():
    container = _container()
    container.auth.seed("t-2", subject="user-1", tenant_id="local", roles=["voice"])
    client = TestClient(create_app(container))
    with client.websocket_connect("/ws/voice") as ws:
        ws.send_json(_start())
        assert ws.receive_json()["kind"] == "session_ready"
        ws.send_json({"type": "refresh_token", "apm_principal_token": "t-2"})
        ws.send_json({"type": "audio", "audio": _AUDIO})
        # A valid refreshed token keeps the turn alive.
        assert ws.receive_json()["kind"] == "transcript"


def test_ws_expired_token_ends_session():
    container = _container()
    client = TestClient(create_app(container))
    with client.websocket_connect("/ws/voice") as ws:
        ws.send_json(_start())
        assert ws.receive_json()["kind"] == "session_ready"
        container.auth.mark_expired("t-1")
        ws.send_json({"type": "audio", "audio": _AUDIO})
        assert ws.receive_json()["kind"] == "error"
        assert ws.receive_json()["kind"] == "session_closed"
