"""Pipecat transport helpers for the voice WebSocket."""

from __future__ import annotations

from typing import Any

from pipecat.pipeline.worker import PipelineWorker
from pipecat.workers.runner import WorkerRunner


class DeferredCloseWebSocket:
    """Wraps a websocket so Pipecat's transport cleanup does not close it.

    The session sends its final events and closes with the right code itself
    once the pipeline has finished, so those events are strictly ordered after
    all media and the close code can be 1008 where required.
    """

    def __init__(self, websocket: Any) -> None:
        self._websocket = websocket

    def __getattr__(self, name: str) -> Any:
        return getattr(self._websocket, name)

    async def close(self, code: int = 1000, reason: str | None = None) -> None:
        return None


async def run_worker(worker: PipelineWorker) -> None:
    runner = WorkerRunner(handle_sigint=False)
    await runner.add_workers(worker)
    await runner.run()
