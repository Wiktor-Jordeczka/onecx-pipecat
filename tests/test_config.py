from onecx_pipecat.config import Settings


def test_defaults_are_typed_and_usable():
    s = Settings()
    assert s.app_name == "onecx-pipecat"
    assert s.port == 8080
    assert s.auth.audience == "onecx-pipecat"
    assert s.speech.sample_rate_hz == 16000
    assert s.permission.default_action == "always_ask"
    assert s.mcp.default_server_name == "inmemory"
    assert s.mcp.servers == {"inmemory": "inmemory"}
    assert s.mcp.timeout_seconds == 30.0


def test_environment_overrides_nested_field(monkeypatch):
    # `__` is the env_nested_delimiter, so ONECX_AUTH__ISSUER maps to auth.issuer.
    monkeypatch.setenv("ONECX_AUTH__ISSUER", "https://other")
    s = Settings(_env_file=None)
    assert s.auth.issuer == "https://other"
