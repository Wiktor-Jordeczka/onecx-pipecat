import pytest
from pydantic import SecretStr

from onecx_pipecat.config import CredentialsSettings, Settings
from onecx_pipecat.services.credentials import CredentialError, CredentialResolver


def _resolver(**refs: str) -> CredentialResolver:
    return CredentialResolver(CredentialsSettings(refs={k: SecretStr(v) for k, v in refs.items()}))


def test_resolves_known_ref():
    assert _resolver(a="s3cret").resolve("a") == "s3cret"


@pytest.mark.parametrize("ref", ["", "  ", "missing"])
def test_unknown_or_blank_ref_raises(ref):
    with pytest.raises(CredentialError):
        _resolver(a="s3cret").resolve(ref)


def test_blank_secret_raises():
    with pytest.raises(CredentialError):
        _resolver(a=" ").resolve("a")


def test_error_never_contains_secret():
    with pytest.raises(CredentialError) as exc:
        _resolver(a="s3cret").resolve("b")
    assert "s3cret" not in str(exc.value)


def test_env_json_map_is_loaded_and_secret_is_not_in_repr(monkeypatch):
    monkeypatch.setenv("ONECX_CREDENTIALS__REFS", '{"credential://p/1/api-key": "sk-topsecret"}')
    settings = Settings()
    assert CredentialResolver(settings.credentials).resolve("credential://p/1/api-key") == (
        "sk-topsecret"
    )
    assert "sk-topsecret" not in repr(settings)
    assert "sk-topsecret" not in settings.model_dump_json()
