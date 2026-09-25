"""Runnable entrypoint: uvicorn onecx_pipecat.main:app --port 8080."""

from __future__ import annotations

import uvicorn

from onecx_pipecat.app import create_app
from onecx_pipecat.config import get_settings
from onecx_pipecat.container import AppContainer

_container = AppContainer(get_settings())
app = create_app(_container)


def run() -> None:
    settings = get_settings()
    uvicorn.run(
        "onecx_pipecat.main:app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level,
    )


if __name__ == "__main__":
    run()
