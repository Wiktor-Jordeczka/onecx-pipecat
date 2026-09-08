from fastapi import FastAPI

from onecx_pipecat.main import app as fastapi_app


def test_main_exposes_a_fastapi_app_with_healthz_route():
    assert isinstance(fastapi_app, FastAPI)
    paths = {r.path for r in fastapi_app.routes}
    assert "/healthz" in paths
