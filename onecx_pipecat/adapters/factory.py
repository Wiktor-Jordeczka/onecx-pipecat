"""Concrete adapter construction from Settings.

OneCX boundaries (auth, agent configuration, chat, permission, MCP) always use
their real implementation; there is no in-memory fallback that a deployment
could silently run on. Speech defaults to the deterministic in-memory adapters;
selecting the ``aws`` provider builds the pinned-language AWS adapters instead.
Persistence stays in-memory until a real adapter exists.
"""

from __future__ import annotations

from onecx_pipecat.adapters.agent_config import HttpAgentConfigAdapter
from onecx_pipecat.adapters.auth import ClientCredentialsAuth, JwtAuthAdapter
from onecx_pipecat.adapters.chat import HttpChatAdapter
from onecx_pipecat.adapters.mcp import HttpMcpAdapter
from onecx_pipecat.adapters.permission import HttpPermissionAdapter
from onecx_pipecat.adapters.persistence import InMemoryPersistence
from onecx_pipecat.adapters.speech import (
    AwsSttAdapter,
    AwsTtsAdapter,
    InMemorySttAdapter,
    InMemoryTtsAdapter,
    resolve_profile,
)
from onecx_pipecat.config import Settings


def build_service_auth(settings: Settings) -> ClientCredentialsAuth:
    return ClientCredentialsAuth(settings.auth)


def build_auth(settings: Settings, service_auth: ClientCredentialsAuth):
    return JwtAuthAdapter(settings.auth, service_auth)


def build_agent_config(settings: Settings, service_auth: ClientCredentialsAuth):
    return HttpAgentConfigAdapter(settings.agent_config, service_auth)


def build_chat(settings: Settings, service_auth: ClientCredentialsAuth):
    return HttpChatAdapter(settings.chat, service_auth)


def build_stt(settings: Settings, language_code: str | None = None):
    """Build an STT adapter for the configured provider and pinned language.

    An empty/omitted ``language_code`` falls back to the configured default
    language. A pinned language with no AWS profile raises
    ``UnsupportedLanguageError`` (surfaced by the caller as a typed error).
    """
    speech = settings.speech
    if speech.stt_provider == "aws":
        profile = resolve_profile(speech, language_code or speech.default_language)
        return AwsSttAdapter(speech, profile)
    return InMemorySttAdapter(speech)


def build_tts(settings: Settings, language_code: str | None = None):
    """Build a TTS adapter for the configured provider and pinned language."""
    speech = settings.speech
    if speech.tts_provider == "aws":
        profile = resolve_profile(speech, language_code or speech.default_language)
        return AwsTtsAdapter(speech, profile)
    return InMemoryTtsAdapter(speech)


def build_persistence(settings: Settings):
    return InMemoryPersistence(settings.persistence)


def build_permission(settings: Settings, service_auth: ClientCredentialsAuth):
    return HttpPermissionAdapter(settings.permission, service_auth)


def build_mcp(settings: Settings):
    # MCP servers are per-agent and may be external: Pipecat's service token is not sent there.
    return HttpMcpAdapter(settings.mcp)
