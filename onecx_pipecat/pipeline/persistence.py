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


def attach_persistence(
    user: LLMUserAggregator,
    assistant: LLMAssistantAggregator,
    save: Callable[[VoiceEntry], Awaitable[str]],
    emit: Emit,
) -> None:
    human_failed = False
    human_save_done: asyncio.Future[None] | None = None

    @user.event_handler("on_user_turn_started")
    async def on_user_turn_started(_aggregator, _strategy, _message) -> None:
        nonlocal human_failed, human_save_done
        human_failed = False
        human_save_done = asyncio.get_running_loop().create_future()

    @user.event_handler("on_user_turn_stopped")
    async def on_user_turn_stopped(_aggregator, _strategy, message) -> None:
        nonlocal human_failed, human_save_done
        if human_save_done is None:
            human_save_done = asyncio.get_running_loop().create_future()
        text = (message.content or "").strip()
        if not text:
            human_save_done.set_result(None)
            return
        try:
            await save(VoiceEntry(kind=VoiceEntryKind.HUMAN, text=text))
        except Exception as exc:  # noqa: BLE001 - reported as a typed error, no fabricated history
            human_failed = True
            await emit(ErrorEvent(code="persistence_failed", message=f"human entry: {exc}"))
        finally:
            if not human_save_done.done():
                human_save_done.set_result(None)

    @assistant.event_handler("on_assistant_turn_stopped")
    async def on_assistant_turn_stopped(_aggregator, message) -> None:
        if human_save_done is not None:
            await human_save_done
        skip = human_failed
        text = message.content.strip()
        if skip or not text:
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
