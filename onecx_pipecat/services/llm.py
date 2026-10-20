"""Build the Pipecat LLM service for the pinned agent's provider and model."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from onecx_pipecat.config import Settings
from onecx_pipecat.models import AgentConfigSnapshot
from onecx_pipecat.services.credentials import CredentialResolver

if TYPE_CHECKING:
    from pipecat.services.llm_service import LLMService

# model_config JSON key (camelCase or snake_case) -> Pipecat LLM settings field.
_PARAM_KEYS: dict[str, str] = {
    "temperature": "temperature",
    "max_tokens": "max_tokens",
    "maxTokens": "max_tokens",
    "top_p": "top_p",
    "topP": "top_p",
}
_INT_PARAMS = {"max_tokens"}

# Placeholder key for OpenAI-compatible endpoints that need none; the client requires a value.
_NO_API_KEY = "not-needed"


class LlmConfigError(Exception):
    """Raised when the pinned provider/model cannot be turned into an LLM service."""


def parse_model_params(raw: str) -> dict[str, Any]:
    """Map the opaque ``modelConfig`` JSON to Pipecat settings; unknown keys are ignored."""
    if not raw or not raw.strip():
        return {}
    try:
        data = json.loads(raw)
    except ValueError as exc:
        raise LlmConfigError("model configuration is not valid JSON") from exc
    if not isinstance(data, dict):
        raise LlmConfigError("model configuration must be a JSON object")
    params: dict[str, Any] = {}
    for key, field in _PARAM_KEYS.items():
        if key not in data or data[key] is None:
            continue
        value = data[key]
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise LlmConfigError(f"model configuration {key!r} must be a number")
        params[field] = int(value) if field in _INT_PARAMS else float(value)
    return params


def build_llm(
    snapshot: AgentConfigSnapshot,
    settings: Settings,
    credentials: CredentialResolver,
) -> LLMService:
    """Create the LLM service for ``snapshot``.

    Raises ``LlmConfigError`` for an unusable provider/model/model_config and
    ``CredentialError`` when the provider's credentialRef cannot be resolved.
    Pipecat service modules are imported lazily so unused providers need no SDK.
    """
    provider, model = snapshot.provider, snapshot.model
    if settings.llm.provider_override == "inmemory":
        from onecx_pipecat.services.inmemory import InMemoryLLM

        return InMemoryLLM()
    if provider is None or model is None:
        raise LlmConfigError("agent configuration has no provider or model")
    params = parse_model_params(model.model_params)
    api_key = _resolve_api_key(provider.auth_mode, provider.credential_ref, credentials)
    ptype = provider.type.upper()

    if ptype == "OPENAI":
        from pipecat.services.openai.llm import OpenAILLMService

        if api_key is None and not provider.llm_url:
            raise LlmConfigError("OPENAI provider requires an API key credential")
        kwargs: dict[str, Any] = {"api_key": api_key or _NO_API_KEY}
        if provider.llm_url:
            kwargs["base_url"] = provider.llm_url
        return OpenAILLMService(
            settings=OpenAILLMService.Settings(model=model.model_identifier, **params), **kwargs
        )

    if ptype == "OLLAMA":
        from pipecat.services.ollama.llm import OLLamaLLMService

        # Pipecat's Ollama service sends a fixed placeholder key; a credential is ignored.
        kwargs = {"base_url": provider.llm_url} if provider.llm_url else {}
        return OLLamaLLMService(
            settings=OLLamaLLMService.Settings(model=model.model_identifier, **params), **kwargs
        )

    if ptype == "ANTHROPIC":
        from pipecat.services.anthropic.llm import AnthropicLLMService

        if api_key is None:
            raise LlmConfigError("ANTHROPIC provider requires an API key credential")
        kwargs = {}
        if provider.llm_url:
            from anthropic import AsyncAnthropic

            kwargs["client"] = AsyncAnthropic(api_key=api_key, base_url=provider.llm_url)
        return AnthropicLLMService(
            api_key=api_key,
            settings=AnthropicLLMService.Settings(model=model.model_identifier, **params),
            **kwargs,
        )

    raise LlmConfigError(f"unsupported LLM provider type: {provider.type!r}")


def _resolve_api_key(
    auth_mode: str, credential_ref: str, credentials: CredentialResolver
) -> str | None:
    mode = auth_mode.upper()
    if mode == "OAUTH":
        raise LlmConfigError("OAUTH provider authentication is not supported")
    if mode == "API_KEY" or credential_ref:
        return credentials.resolve(credential_ref)
    return None
