from types import SimpleNamespace

from onecx_pipecat.models import VoiceEntryKind, VoiceEntryStatus
from onecx_pipecat.pipeline.persistence import attach_persistence
from tests.fakes import FakePersistence


class _Aggregator:
    def __init__(self) -> None:
        self.handlers: dict[str, object] = {}

    def event_handler(self, name):
        def register(fn):
            self.handlers[name] = fn
            return fn

        return register


class _Harness:
    def __init__(self, store: FakePersistence) -> None:
        self.user, self.assistant = _Aggregator(), _Aggregator()
        self.emitted: list = []
        self.store = store

        async def emit(event) -> None:
            self.emitted.append(event)

        async def save(entry) -> str:
            return await store.append("s1", entry)

        attach_persistence(self.user, self.assistant, save, emit)

    async def user_said(self, content) -> None:
        await self.user.handlers["on_user_turn_started"](None, None)
        await self.user.handlers["on_user_turn_stopped"](
            None, None, SimpleNamespace(content=content)
        )

    async def assistant_said(self, content: str, interrupted: bool = False) -> None:
        await self.assistant.handlers["on_assistant_turn_started"](None)
        await self.assistant.handlers["on_assistant_turn_stopped"](
            None, SimpleNamespace(content=content, interrupted=interrupted)
        )


async def test_completed_turn_persists_human_then_assistant_and_acknowledges():
    h = _Harness(FakePersistence())
    await h.user_said("  hello ")
    await h.assistant_said("hi there")
    assert [(e.kind, e.text, e.status) for e in h.store.entries] == [
        (VoiceEntryKind.HUMAN, "hello", VoiceEntryStatus.COMPLETED),
        (VoiceEntryKind.ASSISTANT, "hi there", VoiceEntryStatus.COMPLETED),
    ]
    assert [(e.kind, e.entry_id) for e in h.emitted] == [("turn_complete", "s1:2")]


async def test_interrupted_assistant_turn_is_persisted_as_interrupted():
    h = _Harness(FakePersistence())
    await h.user_said("hello")
    await h.assistant_said("partial", interrupted=True)
    assert h.store.entries[-1].status is VoiceEntryStatus.INTERRUPTED
    assert [e.kind for e in h.emitted] == ["turn_complete"]


async def test_blank_turns_stay_ephemeral():
    h = _Harness(FakePersistence())
    await h.user_said("   ")
    await h.user_said(None)
    await h.assistant_said("  ")
    assert h.store.entries == []
    assert h.emitted == []


async def test_human_persistence_failure_does_not_skip_the_next_turn_after_llm_error():
    store = FakePersistence(fail_human=True)
    h = _Harness(store)
    await h.user_said("hello")
    # The failed LLM turn has no assistant-stopped event to consume the failure.
    assert [(e.kind, e.code) for e in h.emitted] == [("error", "persistence_failed")]
    store.fail_human = False
    await h.user_said("again")
    await h.assistant_said("answer 2")
    assert [e.kind for e in store.entries] == [VoiceEntryKind.HUMAN, VoiceEntryKind.ASSISTANT]
    assert [e.kind for e in h.emitted].count("turn_complete") == 1


async def test_assistant_persistence_failure_emits_error_without_turn_complete():
    h = _Harness(FakePersistence(fail_assistant=True))
    await h.user_said("hello")
    await h.assistant_said("answer")
    assert [e.kind for e in h.store.entries] == [VoiceEntryKind.HUMAN]
    assert [(e.kind, e.code) for e in h.emitted] == [("error", "persistence_failed")]
