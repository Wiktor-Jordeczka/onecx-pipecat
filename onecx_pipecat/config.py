"""Typed application configuration.

Loaded from the environment with a stable prefix so deployments can override
any field without code changes.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AuthSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ONECX_AUTH__")

    issuer: str = "https://auth.example"
    audience: str = "onecx-pipecat"
    token_claim_subject: str = "sub"
    # Keycloak JWKS used to verify ``apm-principal-token``: an embedded JSON
    # document or a URL; empty fetches ``{issuer}/protocol/openid-connect/certs``.
    jwks: str = ""
    # Pipecat's own OIDC client credentials, used to authenticate outbound
    # calls to OneCX services the way a BFF does (apm-principal-token is also
    # propagated to act as the user).
    client_id: str = "onecx-pipecat"
    client_secret: str = ""
    # Empty uses ``{issuer}/protocol/openid-connect/token``.
    token_endpoint: str = ""


class AgentConfigSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ONECX_AGENT_CONFIG__")

    default_agent_id: str = "onecx-agent"
    default_snapshot_version: int = 1
    # Base URL of onecx-ai-provider-svc (``GET /v1/agents/{id}/configuration``).
    base_url: str = "http://onecx-ai-provider-svc:8080"


class ChatSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ONECX_CHAT__")

    # Base URL of onecx-chat-svc, used to load a chat by id as the user.
    base_url: str = "http://onecx-chat-svc:8080"


class SpeechSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ONECX_SPEECH__")

    stt_provider: str = "inmemory"
    tts_provider: str = "inmemory"
    sample_rate_hz: int = 16000


class PersistenceSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ONECX_PERSISTENCE__")

    backend: str = "inmemory"
    max_entries_per_session: int = 512


class PermissionSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ONECX_PERMISSION__")

    # Base URL of onecx-permission-svc (``POST /v1/permissions/user/{productName}/{appId}``).
    base_url: str = "http://onecx-permission-svc:8080"
    # The OneCX permission that grants voice: ``voice_action`` on ``voice_resource``
    # of application ``voice_app_id`` in product ``voice_product_name``.
    voice_product_name: str = "onecx-ai"
    voice_app_id: str = "onecx-ai-ui"
    voice_resource: str = "VOICE"
    voice_action: str = "USE"


class McpSettings(BaseSettings):
    """Operator-level MCP knobs; server URLs come from the agent configuration."""

    model_config = SettingsConfigDict(env_prefix="ONECX_MCP__")

    timeout_seconds: float = 30.0


class Settings(BaseSettings):
    """Root configuration for the Pipecat application.

    Every adapter's knobs live on a nested model so configuration stays
    typed and the environment mapping stays explicit.
    """

    model_config = SettingsConfigDict(env_prefix="ONECX_", env_nested_delimiter="__")

    app_name: str = "onecx-pipecat"
    host: str = "127.0.0.1"
    port: int = 8080
    log_level: str = "INFO"
    default_tenant_id: str = "local"

    auth: AuthSettings = Field(default_factory=AuthSettings)
    agent_config: AgentConfigSettings = Field(default_factory=AgentConfigSettings)
    chat: ChatSettings = Field(default_factory=ChatSettings)
    speech: SpeechSettings = Field(default_factory=SpeechSettings)
    persistence: PersistenceSettings = Field(default_factory=PersistenceSettings)
    permission: PermissionSettings = Field(default_factory=PermissionSettings)
    mcp: McpSettings = Field(default_factory=McpSettings)


@lru_cache
def get_settings() -> Settings:
    """Return a process-wide Settings instance."""
    return Settings()
