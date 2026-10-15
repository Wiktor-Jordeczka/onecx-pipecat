"""Authentication adapter: exchange a credential for a typed Principal.

The wire contract: the client's first message carries the user's
``apm-principal-token`` (and the browser's ``Authorization`` value). The
adapter verifies that token — signature, issuer and expiry for a real
deployment — and reports expiry so a session can end with a typed error when
the tokens lapse without a refresh. ``service_token`` obtains Pipecat's own
OIDC client-credentials token for outbound calls to OneCX services (the
apm-principal-token is propagated on top of it, BFF-style).
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Protocol

from onecx_pipecat.config import AuthSettings
from onecx_pipecat.models import Principal


class AuthenticationError(Exception):
    """Raised when a credential cannot be validated."""


class AuthAdapter(Protocol):
    """Replaceable authentication boundary."""

    async def authenticate(self, token: str) -> Principal: ...

    def is_expired(self, token: str) -> bool:
        """True once the session token has lapsed and cannot be used."""
        ...

    async def refresh(self, token: str) -> Principal:
        """Validate and return the principal for a refreshed token."""
        ...

    async def service_token(self) -> str:
        """A bearer token Pipecat uses for its own outbound service calls."""
        ...


@dataclass
class _InMemoryCredential:
    token: str
    subject: str
    tenant_id: str
    roles: list[str]
    expired: bool = False

    def __post_init__(self) -> None:
        if not self.token or not self.subject or not self.tenant_id:
            raise ValueError("token/subject/tenant_id required")


class InMemoryAuthAdapter:
    """Deterministic token table for local runs and tests.

    Resolves a token against a local table rather than parsing JWTs; an entry
    seeded as expired stands in for a lapsed ``apm-principal-token`` so the
    fail-closed and refresh paths are exercisable offline.
    """

    def __init__(self, settings: AuthSettings | None = None) -> None:
        self._settings = settings or AuthSettings()
        self._table: dict[str, _InMemoryCredential] = {}
        self._service_token: str = ""

    def seed(
        self,
        token: str,
        subject: str,
        tenant_id: str,
        roles: list[str] | None = None,
        *,
        expired: bool = False,
    ) -> None:
        self._table[token] = _InMemoryCredential(
            token=token,
            subject=subject,
            tenant_id=tenant_id,
            roles=list(roles or []),
            expired=expired,
        )

    def mark_expired(self, token: str) -> None:
        """Stand-in for a token whose ``exp`` claim has passed."""
        cred = self._table.get(token)
        if cred is not None:
            cred.expired = True

    def set_service_token(self, token: str) -> None:
        self._service_token = token

    def _principal(self, token: str) -> Principal:
        cred = self._table.get(token)
        if cred is None or cred.expired:
            raise AuthenticationError("unknown or expired token")
        return Principal(subject=cred.subject, tenant_id=cred.tenant_id, roles=list(cred.roles))

    async def authenticate(self, token: str) -> Principal:
        return self._principal(token)

    def is_expired(self, token: str) -> bool:
        cred = self._table.get(token)
        return cred is None or cred.expired

    async def refresh(self, token: str) -> Principal:
        return self._principal(token)

    async def service_token(self) -> str:
        return self._service_token or "pipecat-service-token"


class JwtAuthAdapter:
    """Verify ``apm-principal-token`` against Keycloak's JWKS.

    Validates the signature (RS256), issuer, audience and ``exp`` exactly the
    way ``onecx-permission-svc`` does, using the configured issuer and key set.
    Keys come from ``settings.jwks`` (an embedded JWKS JSON document). This
    class is only constructed by explicit wiring; the default factory uses the
    in-memory stand-in so local runs need no Keycloak access.
    """

    def __init__(self, settings: AuthSettings | None = None) -> None:
        self._settings = settings or AuthSettings()
        self._keys: list[dict] | None = None
        if self._settings.jwks:
            self._keys = self._normalize(self._settings.jwks)

    def set_jwks(self, jwks: object) -> None:
        self._keys = self._normalize(jwks)

    @staticmethod
    def _normalize(jwks: object) -> list[dict]:
        """Turn a JWKS document (dict or JSON string) into its ``keys`` list.

        A bare JWK (dict without a ``keys`` member) or a list of JWKs is also
        accepted, so callers may pass either the full document or the keys.
        """
        if isinstance(jwks, str):
            jwks = json.loads(jwks)
        if isinstance(jwks, dict):
            return list(jwks.get("keys", []))
        if isinstance(jwks, list):
            return [k for k in jwks if isinstance(k, dict)]
        return []

    def _principal(self, claims: dict) -> Principal:
        subject = claims.get(self._settings.token_claim_subject)
        if not isinstance(subject, str) or not subject:
            raise AuthenticationError("token missing subject claim")
        tenant = claims.get("tenant_id", claims.get("azp", "local"))
        roles = claims.get("roles") or []
        if not isinstance(roles, list):
            roles = []
        return Principal(subject=subject, tenant_id=str(tenant), roles=[str(r) for r in roles])

    def _key(self) -> object:
        """The first usable public key from the configured JWKS, or None."""
        if not self._keys:
            return None
        try:
            from jwt import PyJWKSet

            return next(iter(PyJWKSet(self._keys))).key
        except Exception:  # noqa: BLE001 - no usable key configured
            return None

    async def authenticate(self, token: str) -> Principal:
        try:
            import jwt
        except ImportError as exc:  # pragma: no cover - guarded in tests
            raise AuthenticationError("jwt verification unavailable") from exc
        key = self._key()
        if key is None:
            raise AuthenticationError("no JWKS configured")
        try:
            claims = jwt.decode(
                token,
                key=key,
                algorithms=["RS256"],
                audience=self._settings.audience,
                issuer=self._settings.issuer,
            )
        except Exception as exc:  # noqa: BLE001 - all validation failures are auth failures
            raise AuthenticationError(f"token verification failed: {exc}") from exc
        return self._principal(claims)

    def is_expired(self, token: str) -> bool:
        """Verify the signature and read ``exp`` without enforcing it.

        An unparseable, unknown, or untrusted token is treated as lapsed.
        """
        try:
            import jwt
        except ImportError:  # pragma: no cover
            return True
        key = self._key()
        if key is None:
            return True
        try:
            claims = jwt.decode(
                token,
                key=key,
                algorithms=["RS256"],
                audience=self._settings.audience,
                issuer=self._settings.issuer,
                options={"verify_exp": False},
            )
            return int(claims.get("exp", 0)) <= time.time()
        except Exception:  # noqa: BLE001 - untrusted token is treated as lapsed
            return True

    async def refresh(self, token: str) -> Principal:
        return await self.authenticate(token)

    async def service_token(self) -> str:
        # A real deployment exchanges the configured client credentials at the
        # OIDC token endpoint; this stand-in reports the configured client id so
        # the boundary is visible without a live issuer.
        return self._settings.client_id
