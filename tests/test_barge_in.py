import base64

import pytest
from fastapi.testclient import TestClient

from onecx_pipecat import session as session_module
from onecx_pipecat.app import create_app
from onecx_pipecat.models import VoiceEntryKind, VoiceEntryStatus
from onecx_pipecat.services.inmemory import InMemoryLLM, InMemoryTTS
from tests.fakes import FakePersistence, fake_container

_AUDIO = base64.b64encode(b"\x01\x00" * 160).decode("ascii")


@pytest.fixture
def slow_tts(monkeypatch):
    # Pipecat pushes a sentence's text once its audio has played, so a long
    # multi-sentence reply gives the client time to barge in after the first one.
    monkeypatch.setattr(
        session_module,
        "build_llm",
        lambda *args: InMemoryLLM(reply=" ".join(f"Sentence {i}." for i in range(30))),
    )
    monkeypatch.setattr(
        session_module,
        "build_tts_service",
        lambda settings, language: InMemoryTTS(
            sample_rate=settings.speech.sample_rate_hz, chunks=3, chunk_ms=100
        ),
    )


def _until(ws, kind: str) -> list[dict]:
    events = []
    while True:
        events.append(ws.receive_json())
        if events[-1]["kind"] == kind:
            return events


def test_barge_in_interrupts_the_bot_and_persists_an_interrupted_entry(slow_tts):
    container = fake_container(token="t-1")
    persistence = FakePersistence()
    container.persistence = persistence  # type: ignore[assignment]
    client = TestClient(create_app(container))
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
        _until(ws, "assistant_text")

        ws.send_json({"type": "user_started_speaking"})
        events = _until(ws, "turn_complete")
        assert "interrupted" in [e["kind"] for e in events]

        ws.send_json({"type": "stop"})
        _until(ws, "session_closed")

    assistant = [e for e in persistence.entries if e.kind is VoiceEntryKind.ASSISTANT]
    assert [e.status for e in assistant] == [VoiceEntryStatus.INTERRUPTED]


def _start(ws) -> None:
    ws.send_json(
        {
            "type": "start_session",
            "agent_id": "onecx-agent",
            "chat_id": "chat-1",
            "apm_principal_token": "t-1",
        }
    )
    assert ws.receive_json()["kind"] == "session_ready"


def _speak(ws) -> None:
    ws.send_json({"type": "user_started_speaking"})
    ws.send_json({"type": "audio", "audio": _AUDIO})
    ws.send_json({"type": "user_stopped_speaking"})


def test_a_failed_human_save_does_not_drop_the_next_turn():
    container = fake_container(token="t-1")
    persistence = FakePersistence(fail_human=True)
    container.persistence = persistence  # type: ignore[assignment]
    client = TestClient(create_app(container))
    with client.websocket_connect("/ws/voice") as ws:
        _start(ws)
        _speak(ws)
        first = _until(ws, "error")
        assert first[-1]["code"] == "persistence_failed"
        persistence.fail_human = False
        _speak(ws)
        events = _until(ws, "turn_complete")
        assert [e["kind"] for e in events].count("turn_complete") == 1

        ws.send_json({"type": "stop"})
        _until(ws, "session_closed")

    assert [e.kind for e in persistence.entries] == [
        VoiceEntryKind.HUMAN,
        VoiceEntryKind.ASSISTANT,
    ]


def test_barge_in_after_a_slow_human_save_persists_the_interrupted_turn_first(slow_tts):
    container = fake_container(token="t-1")
    persistence = FakePersistence(human_delay=0.3)
    container.persistence = persistence  # type: ignore[assignment]
    client = TestClient(create_app(container))
    with client.websocket_connect("/ws/voice") as ws:
        _start(ws)
        _speak(ws)
        _until(ws, "assistant_text")
        ws.send_json({"type": "user_started_speaking"})
        events = _until(ws, "turn_complete")
        assert "interrupted" in [e["kind"] for e in events]

        ws.send_json({"type": "stop"})
        _until(ws, "session_closed")

    assert [(e.kind, e.status) for e in persistence.entries] == [
        (VoiceEntryKind.HUMAN, VoiceEntryStatus.COMPLETED),
        (VoiceEntryKind.ASSISTANT, VoiceEntryStatus.INTERRUPTED),
    ]
