"""Small OneCX processors around the Pipecat pipeline."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from pipecat.frames.frames import (
    CancelWorkerFrame,
    Frame,
    InputTransportMessageFrame,
    OutputTransportMessageFrame,
    OutputTransportMessageUrgentFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

from onecx_pipecat.pipeline.serializer import BAD_COMMAND, wire_event
from onecx_pipecat.protocol import (
    Command,
    ErrorEvent,
    Event,
    RefreshToken,
    StopSession,
    decode_command,
)

Emit = Callable[[Event], Awaitable[None]]


def message_frame(event: Event, *, urgent: bool) -> Frame:
    message = event.model_dump()
    if urgent:
        return OutputTransportMessageUrgentFrame(message=message)
    return OutputTransportMessageFrame(message=message)


class SessionControl(FrameProcessor):
    """Handles ``refresh_token`` / ``stop`` and malformed commands from the client."""

    def __init__(
        self, dispatch: Callable[[Command], Awaitable[list[Event]]], emit: Emit, **kwargs
    ) -> None:
        super().__init__(name="SessionControl", **kwargs)
        self._dispatch = dispatch
        self._emit = emit

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)
        if not isinstance(frame, InputTransportMessageFrame):
            await self.push_frame(frame, direction)
            return
        message = frame.message if isinstance(frame.message, dict) else BAD_COMMAND
        command = decode_command(message)
        if not isinstance(command, RefreshToken | StopSession):
            await self._emit(ErrorEvent(code="bad_command", message="malformed command"))
        elif isinstance(command, StopSession):
            await self._dispatch(command)
            await self.push_frame(
                CancelWorkerFrame(reason="client_stopped"), FrameDirection.UPSTREAM
            )
        else:
            for event in await self._dispatch(command):
                await self._emit(event)


class WireEvents(FrameProcessor):
    """Mirrors client-visible frames as transport messages, then passes the frame on.

    The output transport only serializes interruptions, transport messages and
    audio, so frames like transcripts, spoken text and bot speaking state need
    an explicit transport message. ``ordered`` messages travel in sequence with
    the audio; ``urgent`` ones are sent immediately.
    """

    def __init__(
        self,
        *,
        urgent: tuple[type[Frame], ...] = (),
        ordered: tuple[type[Frame], ...] = (),
        **kwargs,
    ) -> None:
        super().__init__(name="WireEvents", **kwargs)
        self._urgent = urgent
        self._ordered = ordered

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)
        is_urgent = isinstance(frame, self._urgent)
        if is_urgent or (
            isinstance(frame, self._ordered) and direction is FrameDirection.DOWNSTREAM
        ):
            if (event := wire_event(frame)) is not None:
                await self.push_frame(message_frame(event, urgent=is_urgent))
        await self.push_frame(frame, direction)
