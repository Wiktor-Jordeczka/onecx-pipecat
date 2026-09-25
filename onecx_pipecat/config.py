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


class AgentConfigSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ONECX_AGENT_CONFIG__")

    default_agent_id: str = "onecx-agent"
    default_snapshot_version: int = 1


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


class McpSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ONECX_MCP__")

    default_server_name: str = "inmemory"
    servers: dict[str, str] = Field(default_factory=lambda: {"inmemory": "inmemory"})
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
    speech: SpeechSettings = Field(default_factory=SpeechSettings)
    persistence: PersistenceSettings = Field(default_factory=PersistenceSettings)
    permission: PermissionSettings = Field(default_factory=PermissionSettings)
    mcp: McpSettings = Field(default_factory=McpSettings)


@lru_cache
def get_settings() -> Settings:
    """Return a process-wide Settings instance."""
    return Settings()
