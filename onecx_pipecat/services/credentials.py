"""Resolve ``credentialRef`` values from the agent configuration to secrets.

References come from ai-provider (e.g. ``credential://provider/{id}/api-key``);
the secrets are provisioned by the operator in ``ONECX_CREDENTIALS__REFS``.
"""

from __future__ import annotations

from onecx_pipecat.config import CredentialsSettings


class CredentialError(Exception):
    """Raised when a credential reference cannot be resolved (fail closed)."""


class CredentialResolver:
    def __init__(self, settings: CredentialsSettings | None = None) -> None:
        self._refs = (settings or CredentialsSettings()).refs

    def resolve(self, ref: str) -> str:
        """Return the secret for ``ref``; errors never include the secret."""
        if not ref or not ref.strip():
            raise CredentialError("credential reference is empty")
        secret = self._refs.get(ref)
        if secret is None:
            raise CredentialError(f"unknown credential reference: {ref!r}")
        value = secret.get_secret_value()
        if not value.strip():
            raise CredentialError(f"credential for reference {ref!r} is blank")
        return value
