from onecx_pipecat.config import Settings
from onecx_pipecat.container import AppContainer
from onecx_pipecat.models import Principal, VoiceEntryKind
from onecx_pipecat.protocol import ClientAudio, StartSession, StopSession
from onecx_pipecat.session import SessionState, VoiceSession


def _container() -> AppContainer:
    container = AppContainer(Settings())
    container.agent_config.register("local", "onecx-agent", 1, system_prompt="be brief")
    return container


def _session(container: AppContainer) -> VoiceSession:
    principal = Principal(subject="user-1", tenant_id="local", roles=["voice"])
    return VoiceSession("sess-1", principal, container)


async def test_start_becomes_ready_with_pinned_version():
    session = _session(_container())
    events = await session.dispatch(StartSession(agent_id="onecx-agent"))
    assert session.state is SessionState.READY
    assert [e.kind for e in events] == ["session_ready"]
    assert events[0].agent_version == 1


async def test_start_without_configuration_fails_closed():
    session = _session(AppContainer(Settings()))
    events = await session.dispatch(StartSession(agent_id="onecx-agent"))
    assert session.state is SessionState.CREATED
    assert events[0].kind == "error"
    assert events[0].code == "config_unavailable"


async def test_audio_before_start_is_rejected():
    session = _session(_container())
    events = await session.dispatch(ClientAudio(audio=b"pcm"))
    assert events[0].kind == "error"
    assert events[0].code == "illegal_state"


async def test_second_start_is_rejected():
    session = _session(_container())
    await session.dispatch(StartSession(agent_id="onecx-agent"))
    events = await session.dispatch(StartSession(agent_id="onecx-agent"))
    assert events[0].kind == "error"
    assert events[0].code == "illegal_state"


async def test_audio_turn_emits_transcript_text_audio_and_completion():
    container = _container()
    session = _session(container)
    await session.dispatch(StartSession(agent_id="onecx-agent"))
    events = await session.dispatch(ClientAudio(audio=b"pcm"))
    kinds = [e.kind for e in events]
    assert kinds == ["transcript", "assistant_text", "assistant_audio", "turn_complete"]
    assert events[0].state == "FINAL"
    assert events[1].status == "COMPLETED"


async def test_empty_transcript_stays_ephemeral():
    session = _session(_container())
    await session.dispatch(StartSession(agent_id="onecx-agent"))
    events = await session.dispatch(ClientAudio(audio=b""))
    assert events == []


async def test_turn_persists_human_and_assistant_entries():
    container = _container()
    session = _session(container)
    await session.dispatch(StartSession(agent_id="onecx-agent"))
    await session.dispatch(ClientAudio(audio=b"pcm"))
    entries = await container.persistence.list_entries("sess-1")
    kinds = [entry.kind for entry in entries]
    assert kinds == [VoiceEntryKind.HUMAN, VoiceEntryKind.ASSISTANT]


async def test_stop_closes_the_session():
    session = _session(_container())
    await session.dispatch(StartSession(agent_id="onecx-agent"))
    events = await session.dispatch(StopSession())
    assert session.state is SessionState.CLOSED
    assert events[0].kind == "session_closed"
