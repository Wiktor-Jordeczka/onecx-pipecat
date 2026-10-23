"""Durable voice entries, written from the context aggregators' turn events.

A user turn is persisted as a HUMAN entry when it ends with non-blank text; an
assistant turn as an ASSISTANT entry, COMPLETED or INTERRUPTED. Pipecat starts
the LLM before ``on_user_turn_stopped`` fires, so a HUMAN persistence failure
cannot prevent the reply: the error is reported and the reply of that turn is
neither persisted nor acknowledged with ``turn_complete``.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from onecx_pipecat.models import VoiceEntry, VoiceEntryKind, VoiceEntryStatus
from onecx_pipecat.pipeline.processors import Emit
from onecx_pipecat.protocol import ErrorEvent, TurnComplete

if TYPE_CHECKING:
    from pipecat.processors.aggregators.llm_response_universal import (
        LLMAssistantAggregator,
        LLMUserAggregator,
    )


class _UserTurn:
    """Outcome of one user turn's HUMAN save, awaited by the assistant turn that answers it."""

    def __init__(self) -> None:
        self.saved: asyncio.Future[None] = asyncio.get_running_loop().create_future()
        self.failed = False

    def settle(self) -> None:
        if not self.saved.done():
            self.saved.set_result(None)


def attach_persistence(
    user: LLMUserAggregator,
    assistant: LLMAssistantAggregator,
    save: Callable[[VoiceEntry], Awaitable[str]],
    emit: Emit,
) -> None:
    # The turn being collected, and the turn the running assistant reply answers.
    # They differ after a barge-in: the next user turn starts before the
    # interrupted assistant turn stops.
    current: _UserTurn | None = None
    answering: _UserTurn | None = None

    @user.event_handler("on_user_turn_started")
    async def on_user_turn_started(_aggregator, _strategy) -> None:
        nonlocal current
        current = _UserTurn()

    @user.event_handler("on_user_turn_stopped")
    async def on_user_turn_stopped(_aggregator, _strategy, message) -> None:
        nonlocal current
        if current is None:
            current = _UserTurn()
        turn = current
        text = (message.content or "").strip()
        if not text:
            turn.settle()
            return
        try:
            await save(VoiceEntry(kind=VoiceEntryKind.HUMAN, text=text))
        except Exception as exc:  # noqa: BLE001 - reported as a typed error, no fabricated history
            turn.failed = True
            await emit(ErrorEvent(code="persistence_failed", message=f"human entry: {exc}"))
        finally:
            turn.settle()

    @assistant.event_handler("on_assistant_turn_started")
    async def on_assistant_turn_started(_aggregator) -> None:
        nonlocal answering
        answering = current

    @assistant.event_handler("on_assistant_turn_stopped")
    async def on_assistant_turn_stopped(_aggregator, message) -> None:
        turn = answering or current
        if turn is not None:
            await turn.saved
        text = message.content.strip()
        if (turn is not None and turn.failed) or not text:
            return
        status = VoiceEntryStatus.INTERRUPTED if message.interrupted else VoiceEntryStatus.COMPLETED
        try:
            entry_id = await save(
                VoiceEntry(kind=VoiceEntryKind.ASSISTANT, text=text, status=status)
            )
        except Exception as exc:  # noqa: BLE001
            await emit(ErrorEvent(code="persistence_failed", message=f"assistant entry: {exc}"))
            return
        await emit(TurnComplete(entry_id=entry_id))
