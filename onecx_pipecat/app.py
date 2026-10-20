"""FastAPI application for the Pipecat foundation."""

from __future__ import annotations

import asyncio
import json
from dataclasses import asdict
from importlib import metadata
from uuid import uuid4

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from onecx_pipecat.container import AppContainer
from onecx_pipecat.protocol import ErrorEvent, Event, decode_command
from onecx_pipecat.session import SessionState, VoiceSession

# WebSocket close code for an unauthenticated or otherwise rejected connection.
_WS_POLICY_VIOLATION = 1008


def _pipecat_version() -> str:
    try:
        return metadata.version("pipecat-ai")
    except metadata.PackageNotFoundError:
        return "unknown"


def create_app(container: AppContainer, expiry_check_seconds: float = 5.0) -> FastAPI:
    app = FastAPI(title=container.settings.app_name)

    @app.get("/healthz")
    async def healthz() -> dict:
        return {
            "status": "OK",
            "app": container.settings.app_name,
            "pipecat_version": _pipecat_version(),
            "adapters": asdict(container.adapters()),
        }

    @app.websocket("/ws/voice")
    async def voice(websocket: WebSocket) -> None:
        # Tokens belong in the first message, not the URL, and the endpoint takes
        # no query parameters at all: any of them is rejected.
        if websocket.query_params:
            await websocket.close(code=_WS_POLICY_VIOLATION)
            return

        await websocket.accept()
        session = VoiceSession(uuid4().hex, container)
        send_lock = asyncio.Lock()

        async def send(events: list[Event]) -> None:
            async with send_lock:
                for event in events:
                    await websocket.send_json(event.model_dump())

        # Voice-turn events stream out of the background turn (captions, audio,
        # completion) one at a time, not as a batch; route them to the socket.
        async def stream(event: Event) -> None:
            await send([event])

        session.set_event_sink(stream)

        async def watch_expiry() -> None:
            # An idle session must end at token expiry, not only when audio arrives.
            while True:
                await asyncio.sleep(expiry_check_seconds)
                if events := session.check_expiry():
                    await send(events)
                    await websocket.close(code=_WS_POLICY_VIOLATION)
                    return

        watcher = asyncio.create_task(watch_expiry())
        try:
            while True:
                raw = await websocket.receive_text()
                try:
                    payload = json.loads(raw)
                except json.JSONDecodeError:
                    payload = None
                command = decode_command(payload) if isinstance(payload, dict) else None
                if command is None:
                    # The first message must be a valid ``start_session``; an
                    # invalid or unknown command is reported and ignored.
                    await send([ErrorEvent(code="bad_command", message="malformed command")])
                    continue
                await send(await session.dispatch(command))
                if session.state is SessionState.CLOSED:
                    if session.start_failed:
                        await websocket.close(code=_WS_POLICY_VIOLATION)
                    break
        except WebSocketDisconnect:
            return
        finally:
            # Stop or disconnect ends the run: release the turn's pipeline and
            # adapter resources (a reconnect starts a new session). A clean
            # ``stop`` already released the turn, and ``release`` is idempotent.
            await session.release()
            watcher.cancel()

    return app
