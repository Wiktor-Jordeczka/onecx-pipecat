"""Permission: the user's OneCX voice permission and per-tool policy.

Two distinct concerns:

* ``PermissionAdapter`` asks onecx-permission-svc whether the user already
  holds the OneCX voice permission (``POST /internal/permissions/me``).
* ``resolve_tool_permission`` / ``allowed_tools`` apply the per-tool policy
  ai-provider already resolved into the pinned agent configuration; only
  ``ALWAYS_ALLOW`` tools are advertised.
"""

from __future__ import annotations

from typing import Any, Protocol

import httpx

from onecx_pipecat.config import PermissionSettings
from onecx_pipecat.models import (
    AgentConfigSnapshot,
    AgentToolSnapshot,
    PermissionAction,
    Principal,
)


class PermissionAdapter(Protocol):
    async def has_voice_permission(self, principal: Principal, apm_principal_token: str) -> bool:
        """Whether the user already has the OneCX voice permission."""
        ...


class HttpPermissionAdapter:
    """Check the voice permission via onecx-permission-svc ``POST /internal/permissions/me``.

    The user's permissions are resolved from ``apm-principal-token`` and paged
    through until the configured voice permission is found. Any error fails
    closed (no voice permission).
    """

    def __init__(
        self, settings: PermissionSettings | None = None, service_auth: httpx.Auth | None = None
    ) -> None:
        self._settings = settings or PermissionSettings()
        self._service_auth = service_auth
        self._client: httpx.AsyncClient | None = None

    def set_client(self, client: httpx.AsyncClient) -> None:
        """Inject a client (used by tests to avoid a live network call)."""
        self._client = client

    async def has_voice_permission(self, principal: Principal, apm_principal_token: str) -> bool:
        client = self._client or httpx.AsyncClient()
        try:
            return await self._search(client, apm_principal_token)
        except (httpx.HTTPError, ValueError):
            return False
        finally:
            if self._client is None:
                await client.aclose()

    async def _search(self, client: httpx.AsyncClient, apm_principal_token: str) -> bool:
        url = f"{self._settings.base_url}/internal/permissions/me"
        headers = {"apm-principal-token": apm_principal_token}
        page = 0
        while True:
            response = await client.post(
                url,
                headers=headers,
                auth=self._service_auth,
                json={
                    "token": apm_principal_token,
                    "pageNumber": page,
                    "pageSize": self._settings.page_size,
                },
            )
            if not response.is_success:
                return False
            body: dict[str, Any] = response.json()
            if any(self._is_voice(p) for p in body.get("stream") or []):
                return True
            page += 1
            if page >= int(body.get("totalPages") or 0):
                return False

    def _is_voice(self, permission: dict[str, Any]) -> bool:
        return (
            permission.get("productName") == self._settings.voice_product_name
            and permission.get("resource") == self._settings.voice_resource
            and permission.get("action") == self._settings.voice_action
        )


def resolve_tool_permission(
    snapshot: AgentConfigSnapshot, tool: AgentToolSnapshot
) -> PermissionAction:
    """The tool rule of the tool's MCP server, else that server's unlisted policy.

    A tool from a server that is not in the snapshot is denied.
    """
    server = next((s for s in snapshot.mcp_servers if s.name == tool.server_name), None)
    if server is None:
        return PermissionAction.DENY
    for rule in server.tool_rules:
        if rule.tool_name == tool.tool_name:
            return rule.permission
    return server.unlisted_tool_permission


def allowed_tools(
    snapshot: AgentConfigSnapshot, discovered: list[AgentToolSnapshot]
) -> list[AgentToolSnapshot]:
    """Only tools resolved to ``ALWAYS_ALLOW`` are advertised."""
    return [
        t
        for t in discovered
        if resolve_tool_permission(snapshot, t) is PermissionAction.ALWAYS_ALLOW
    ]
