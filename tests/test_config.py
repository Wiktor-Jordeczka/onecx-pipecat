from onecx_pipecat.config import Settings


def test_defaults_are_typed_and_usable():
    s = Settings()
    assert s.app_name == "onecx-pipecat"
    assert s.port == 8080
    assert s.auth.audience == "onecx-pipecat"
    assert s.speech.sample_rate_hz == 16000
    assert s.permission.voice_resource == "VOICE"
    assert s.mcp.timeout_seconds == 30.0


def test_mcp_servers_are_not_global_settings():
    # MCP server URLs come from each agent's configuration, never from settings.
    s = Settings()
    assert set(type(s.mcp).model_fields) == {"timeout_seconds"}


def test_auth_settings_carry_keycloak_and_oidc_client():
    s = Settings()
    # Keycloak issuer + JWKS for verifying apm-principal-token.
    assert s.auth.issuer == "https://auth.example"
    assert s.auth.jwks == ""
    # Pipecat's own OIDC client credentials for outbound service calls; an empty
    # token endpoint is derived from the issuer.
    assert s.auth.client_id == "onecx-pipecat"
    assert s.auth.token_endpoint == ""


def test_service_base_urls_default_to_cluster_services():
    s = Settings()
    assert s.chat.base_url == "http://onecx-chat-svc:8080"
    assert s.permission.base_url == "http://onecx-permission-svc:8080"
    assert s.agent_config.base_url == "http://onecx-ai-provider-svc:8080"


def test_environment_overrides_nested_field(monkeypatch):
    # `__` is the env_nested_delimiter, so ONECX_AUTH__ISSUER maps to auth.issuer.
    monkeypatch.setenv("ONECX_AUTH__ISSUER", "https://other")
    s = Settings(_env_file=None)
    assert s.auth.issuer == "https://other"


def test_chat_base_url_env_override(monkeypatch):
    monkeypatch.setenv("ONECX_CHAT__BASE_URL", "https://chat.other")
    s = Settings(_env_file=None)
    assert s.chat.base_url == "https://chat.other"
