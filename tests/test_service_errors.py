import base64

from fastapi.testclient import TestClient
from pipecat.frames.frames import LLMContextFrame
from pipecat.processors.frame_processor import FrameDirection

from onecx_pipecat import session as session_module
from onecx_pipecat.app import create_app
from onecx_pipecat.services.inmemory import InMemoryLLM
from tests.fakes import fake_container

_AUDIO = base64.b64encode(b"\x01\x00" * 160).decode("ascii")


class FailingLLM(InMemoryLLM):
    async def process_frame(self, frame, direction: FrameDirection) -> None:
        if isinstance(frame, LLMContextFrame):
            await self.push_error("boom")
            return
        await super().process_frame(frame, direction)


def test_llm_failure_is_a_typed_non_fatal_error(monkeypatch):
    monkeypatch.setattr(session_module, "build_llm", lambda *args: FailingLLM())
    client = TestClient(create_app(fake_container(token="t-1")))
    with client.websocket_connect("/ws/voice") as ws:
        ws.send_json(
            {
                "type": "start_session",
                "agent_id": "onecx-agent",
                "chat_id": "chat-1",
                "apm_principal_token": "t-1",
            }
        )
        assert ws.receive_json()["kind"] == "session_ready"
        ws.send_json({"type": "user_started_speaking"})
        ws.send_json({"type": "audio", "audio": _AUDIO})
        ws.send_json({"type": "user_stopped_speaking"})
        events = []
        while not events or events[-1]["kind"] != "error":
            events.append(ws.receive_json())
        assert events[-1]["code"] == "llm_failed"

        ws.send_json({"type": "stop"})
        while ws.receive_json()["kind"] != "session_closed":
            pass
