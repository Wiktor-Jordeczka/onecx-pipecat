import warnings

import pytest
from pydantic import SecretStr

from onecx_pipecat.config import CredentialsSettings, Settings
from onecx_pipecat.models import AgentConfigSnapshot, ModelSnapshot, ProviderSnapshot
from onecx_pipecat.services.credentials import CredentialError, CredentialResolver
from onecx_pipecat.services.llm import LlmConfigError, build_llm, parse_model_params

_REF = "credential://provider/p1/api-key"


def _snap(ptype="OPENAI", *, url="", auth="API_KEY", ref=_REF, params="", ident="m-1"):
    return AgentConfigSnapshot(
        agent_id="a",
        schema_version="1",
        provider=ProviderSnapshot(type=ptype, llm_url=url, auth_mode=auth, credential_ref=ref),
        model=ModelSnapshot(model_identifier=ident, model_params=params),
    )


def _build(snapshot):
    creds = CredentialResolver(CredentialsSettings(refs={_REF: SecretStr("sk-test")}))
    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        return build_llm(snapshot, Settings(), creds)


def test_openai():
    from pipecat.services.openai.llm import OpenAILLMService

    llm = _build(
        _snap(url="https://llm.example/v1", params='{"temperature": 0.3, "maxTokens": 99}')
    )
    assert isinstance(llm, OpenAILLMService)
    assert llm._settings.model == "m-1"
    assert llm._settings.temperature == 0.3
    assert llm._settings.max_tokens == 99


def test_openai_without_key_needs_base_url():
    with pytest.raises(LlmConfigError):
        _build(_snap(auth="", ref=""))
    assert _build(_snap(auth="", ref="", url="http://local:1234/v1")) is not None


def test_ollama():
    from pipecat.services.ollama.llm import OLLamaLLMService

    llm = _build(_snap("OLLAMA", url="http://ollama:11434/v1", auth="", ref=""))
    assert isinstance(llm, OLLamaLLMService)
    assert llm._settings.model == "m-1"


def test_anthropic():
    from pipecat.services.anthropic.llm import AnthropicLLMService

    llm = _build(_snap("ANTHROPIC", params='{"top_p": 0.5}'))
    assert isinstance(llm, AnthropicLLMService)
    assert llm._settings.top_p == 0.5


def test_anthropic_with_custom_url_and_without_key():
    assert _build(_snap("ANTHROPIC", url="https://proxy.example")) is not None
    with pytest.raises(LlmConfigError):
        _build(_snap("ANTHROPIC", auth="", ref=""))


def test_unknown_credential_ref_fails_closed():
    with pytest.raises(CredentialError):
        _build(_snap(ref="credential://other"))


@pytest.mark.parametrize(
    "snapshot",
    [
        _snap("BEDROCK"),
        _snap(auth="OAUTH"),
        _snap(params="{not json"),
        _snap(params="[1]"),
        _snap(params='{"temperature": "hot"}'),
        AgentConfigSnapshot(agent_id="a", schema_version="1"),
    ],
)
def test_invalid_config_raises(snapshot):
    with pytest.raises(LlmConfigError):
        _build(snapshot)


def test_parse_model_params_ignores_unknown_keys():
    assert parse_model_params('{"temperature": 1, "foo": "bar", "max_tokens": 5.0}') == {
        "temperature": 1.0,
        "max_tokens": 5,
    }
    assert parse_model_params("") == {}
