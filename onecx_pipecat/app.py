"""FastAPI application for the Pipecat foundation."""

from __future__ import annotations

import json
from dataclasses import asdict
from importlib import metadata
from uuid import uuid4

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from onecx_pipecat.container import AppContainer
from onecx_pipecat.protocol import ErrorEvent, decode_command
from onecx_pipecat.session import SessionState, VoiceSession

# WebSocket close code for an unauthenticated or otherwise rejected connection.
_WS_POLICY_VIOLATION = 1008


def _pipecat_version() -> str:
    try:
        return metadata.version("pipecat-ai")
    except metadata.PackageNotFoundError:
        return "unknown"


def create_app(container: AppContainer) -> FastAPI:
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
        # Tokens belong in the first message, not the URL. A connection that
        # still tries to carry a token in the query string is rejected.
        if websocket.query_params.get("token"):
            await websocket.close(code=_WS_POLICY_VIOLATION)
            return

        await websocket.accept()
        session = VoiceSession(uuid4().hex, container)
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
                    await websocket.send_json(
                        ErrorEvent(code="bad_command", message="malformed command").model_dump()
                    )
                    continue
                for event in await session.dispatch(command):
                    await websocket.send_json(event.model_dump())
                if session.state is SessionState.CLOSED:
                    break
        except WebSocketDisconnect:
            return

    return app
