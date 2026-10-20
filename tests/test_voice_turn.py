"""VoiceTurn: a durable turn driven by a real Pipecat pipeline, end to end.

Each test runs one turn through a real ``Pipeline`` of the OneCX STT/TTS
bridges, with controlled streaming adapters (see :mod:`tests.fakes`) standing
in for AWS Transcribe/Polly and a recording persistence. This covers streaming
(partials never persisted, audio emitted incrementally), terminal writes (one
``HUMAN`` + one ``ASSISTANT`` entry, each in a terminal state), barge-in, and
typed failures that fabricate no history.
"""

from __future__ import annotations

import asyncio

from onecx_pipecat.models import VoiceEntryKind, VoiceEntryStatus
from onecx_pipecat.voice_turn import VoiceTurn
from tests.fakes import Collector, FakePersistence, FakeStt, FakeTts


def _turn(stt, tts, pers, sink):
    return VoiceTurn(
        stt=stt, tts=tts, on_event=sink, persistence=pers, session_id="sess", sample_rate_hz=16000
    )


async def test_natural_completion_streams_and_finalizes():
    sink = Collector()
    pers = FakePersistence()
    turn = _turn(FakeStt(), FakeTts(), pers, sink)
    await turn.run(b"pcm")
    await turn.release()

    # Partials stream, then the final transcript, the caption, audio, completion.
    states = [e.state for e in sink.events if e.kind == "transcript"]
    assert "PARTIAL" in states and states[-1] == "FINAL"
    assert sink.kinds.index("turn_complete") == len(sink.kinds) - 1
    audio_states = [e.state for e in sink.events if e.kind == "assistant_audio"]
    assert all(s == "SYNTHESIZING" for s in audio_states) and audio_states  # incremental
    # Exactly one HUMAN and one ASSISTANT entry, each terminal.
    assert [(e.kind, e.status) for e in pers.entries] == [
        (VoiceEntryKind.HUMAN, VoiceEntryStatus.COMPLETED),
        (VoiceEntryKind.ASSISTANT, VoiceEntryStatus.COMPLETED),
    ]
    assert turn.assistant_entry_id is not None


async def test_barge_in_finalizes_as_interrupted_with_the_text_emitted_so_far():
    sink = Collector()
    pers = FakePersistence()
    # A slow TTS stream so some audio is in flight when the barge-in lands.
    turn = _turn(FakeStt(sleep=0.0), FakeTts([b"a", b"b", b"c"], sleep=0.02), pers, sink)
    task = asyncio.create_task(turn.run(b"pcm"))
    await asyncio.sleep(0.05)  # let the caption and some audio stream out
    await turn.barge_in()
    await task
    await turn.release()

    audio_states = [e.state for e in sink.events if e.kind == "assistant_audio"]
    assert audio_states and all(s == "SYNTHESIZING" for s in audio_states)
    # The assistant entry is written once, in the INTERRUPTED terminal state,
    # with whatever caption was emitted; the turn still completes.
    assert [(e.kind, e.status) for e in pers.entries] == [
        (VoiceEntryKind.HUMAN, VoiceEntryStatus.COMPLETED),
        (VoiceEntryKind.ASSISTANT, VoiceEntryStatus.INTERRUPTED),
    ]
    assert "turn_complete" in sink.kinds


async def test_barge_in_before_anything_is_emitted_writes_no_assistant_entry():
    sink = Collector()
    pers = FakePersistence()
    # A slow STT stream so the final (and thus the caption) has not arrived when
    # the barge-in lands; nothing assistant-side has been emitted yet.
    turn = _turn(FakeStt(sleep=0.05), FakeTts(), pers, sink)
    task = asyncio.create_task(turn.run(b"pcm"))
    await asyncio.sleep(0.01)
    await turn.barge_in()
    await task
    await turn.release()

    assert pers.entries == []  # no HUMAN (no final yet), no ASSISTANT (nothing emitted)
    assert "turn_complete" not in sink.kinds


async def test_empty_input_stays_ephemeral():
    sink = Collector()
    pers = FakePersistence()
    turn = _turn(FakeStt(), FakeTts(), pers, sink)
    await turn.run(b"")
    await turn.release()
    assert sink.events == []
    assert pers.entries == []
    assert turn.assistant_entry_id is None


async def test_stt_failure_emits_a_typed_error_and_writes_nothing():
    sink = Collector()
    pers = FakePersistence()
    turn = _turn(FakeStt(fail=True), FakeTts(), pers, sink)
    await turn.run(b"pcm")
    await turn.release()
    assert [e.code for e in sink.events if e.kind == "error"] == ["stt_failed"]
    assert "turn_complete" not in sink.kinds
    assert pers.entries == []


async def test_tts_failure_keeps_the_text_and_emits_a_typed_error():
    sink = Collector()
    pers = FakePersistence()
    turn = _turn(FakeStt(), FakeTts(fail=True), pers, sink)
    await turn.run(b"pcm")
    await turn.release()
    codes = [e.code for e in sink.events if e.kind == "error"]
    assert codes == ["tts_failed"]
    # The assistant text was kept (persisted COMPLETED) and the turn completed.
    assert [e.state for e in sink.events if e.kind == "assistant_audio"] == ["FAILED"]
    assert [(e.kind, e.status) for e in pers.entries] == [
        (VoiceEntryKind.HUMAN, VoiceEntryStatus.COMPLETED),
        (VoiceEntryKind.ASSISTANT, VoiceEntryStatus.COMPLETED),
    ]
    assert "turn_complete" in sink.kinds


async def test_human_persistence_failure_stops_the_turn_without_fabrication():
    sink = Collector()
    pers = FakePersistence(fail_human=True)
    turn = _turn(FakeStt(), FakeTts(), pers, sink)
    await turn.run(b"pcm")
    await turn.release()
    assert [e.code for e in sink.events if e.kind == "error"] == ["persistence_failed"]
    # The final transcript streamed, but no assistant turn or completion is invented.
    assert "assistant_text" not in sink.kinds
    assert "turn_complete" not in sink.kinds
    assert pers.entries == []


async def test_assistant_persistence_failure_reports_the_error_without_completion():
    sink = Collector()
    pers = FakePersistence(fail_assistant=True)
    turn = _turn(FakeStt(), FakeTts(), pers, sink)
    await turn.run(b"pcm")
    await turn.release()
    assert [e.code for e in sink.events if e.kind == "error"] == ["persistence_failed"]
    # The HUMAN entry persisted and the caption streamed, but the assistant write
    # failed, so no completion event fires.
    assert [e.kind for e in pers.entries] == [VoiceEntryKind.HUMAN]
    assert "turn_complete" not in sink.kinds


async def test_release_is_idempotent_and_cleans_up_the_pipeline():
    sink = Collector()
    pers = FakePersistence()
    turn = _turn(FakeStt(), FakeTts(), pers, sink)
    await turn.run(b"pcm")
    await turn.release()
    await turn.release()  # releasing an already-released turn is a no-op
    assert pers.entries  # the turn still ran to its terminal state
