"""Authentication adapter: exchange a credential for a typed Principal."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from onecx_pipecat.config import AuthSettings
from onecx_pipecat.models import Principal


class AuthenticationError(Exception):
    """Raised when a credential cannot be validated."""


class AuthAdapter(Protocol):
    """Replaceable authentication boundary."""

    async def authenticate(self, token: str) -> Principal: ...


@dataclass
class _InMemoryCredential:
    token: str
    subject: str
    tenant_id: str
    roles: list[str]

    def __post_init__(self) -> None:
        if not self.token or not self.subject or not self.tenant_id:
            raise ValueError("token/subject/tenant_id required")


class InMemoryAuthAdapter:
    """Deterministic token table for local runs and tests."""

    def __init__(self, settings: AuthSettings | None = None) -> None:
        self._settings = settings or AuthSettings()
        self._table: dict[str, _InMemoryCredential] = {}

    def seed(
        self, token: str, subject: str, tenant_id: str, roles: list[str] | None = None
    ) -> None:
        self._table[token] = _InMemoryCredential(
            token=token, subject=subject, tenant_id=tenant_id, roles=list(roles or [])
        )

    async def authenticate(self, token: str) -> Principal:
        cred = self._table.get(token)
        if cred is None:
            raise AuthenticationError("unknown token")
        return Principal(subject=cred.subject, tenant_id=cred.tenant_id, roles=list(cred.roles))
