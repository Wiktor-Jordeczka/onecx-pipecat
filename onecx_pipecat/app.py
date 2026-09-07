"""FastAPI application for the Pipecat foundation."""

from __future__ import annotations

from dataclasses import asdict
from importlib import metadata

from fastapi import FastAPI

from onecx_pipecat.container import AppContainer


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

    return app
