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
    # Keycloak JWKS (embedded JSON or a URL the adapter fetches once) used to
    # verify ``apm-principal-token`` signature, issuer and expiry.
    jwks: str = ""
    # Pipecat's own OIDC client credentials, used to authenticate outbound
    # calls to OneCX services the way a BFF does (apm-principal-token is also
    # propagated to act as the user).
    client_id: str = "onecx-pipecat"
    client_secret: str = ""
    token_endpoint: str = "https://auth.example/protocol/openid-connect/token"
    # Which auth adapter the factory builds: "inmemory" (default) or "jwt"
    # (verifies ``apm-principal-token`` against the Keycloak JWKS). Selecting
    # the real adapter is a configuration change, not a code change.
    backend: str = "inmemory"


class AgentConfigSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ONECX_AGENT_CONFIG__")

    default_agent_id: str = "onecx-agent"
    default_snapshot_version: int = 1
    # Base URL of the service exposing ``GET /v1/agents/{agent_id}/configuration``.
    base_url: str = "https://agentsvc.example"
    # Which agent-config adapter the factory builds: "inmemory" (default) or
    # "http" (calls the configuration endpoint). Selecting a real adapter is a
    # configuration change, not a code change.
    backend: str = "inmemory"


class ChatSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ONECX_CHAT__")

    # Base URL of onecx-chat-svc, used to load a chat by id as the user.
    base_url: str = "https://chat.example"
    # Which chat adapter the factory builds: "inmemory" (default) or "http"
    # (calls onecx-chat-svc). Selecting a real adapter is a configuration
    # change, not a code change.
    backend: str = "inmemory"


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

    default_action: str = "always_ask"
    # Base URL of onecx-permission-svc, used to check the user's existing voice
    # permission through the existing permission interface.
    base_url: str = "https://permissions.example"


class McpSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ONECX_MCP__")

    default_server_name: str = "inmemory"
    servers: dict[str, str] = Field(default_factory=lambda: {"inmemory": "inmemory"})
    timeout_seconds: float = 30.0
    # Which MCP adapter the factory builds: "inmemory" (default) or "http"
    # (discovers tools over the configured HTTP servers). Selecting a real
    # adapter is a configuration change, not a code change.
    backend: str = "inmemory"


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
