"""Chat adapter: load a chat by id as the user.

A voice session starts against an existing chat; loading it as the user (the
``apm-principal-token`` is propagated so the call acts on the user's behalf)
is the first eligibility check. A missing or forbidden chat is a typed
``ChatAccessError`` so the session can fail closed.
"""

from __future__ import annotations

from typing import Any, Protocol

import httpx

from onecx_pipecat.config import ChatSettings


class ChatAccessError(Exception):
    """Raised when the requested chat is missing, forbidden, or the service is
    unreachable — i.e. the user may not voice in this chat."""


class Chat(Protocol):
    """The chat a voice session is anchored to."""

    chat_id: str
    topic: str


class _Chat:
    """The subset of the onecx-chat-svc ``Chat`` record a session needs."""

    def __init__(self, chat_id: str, topic: str = "") -> None:
        self.chat_id = chat_id
        self.topic = topic


class ChatAdapter(Protocol):
    """Replaceable onecx-chat-svc boundary."""

    async def load(self, chat_id: str, apm_principal_token: str) -> Chat: ...


class HttpChatAdapter:
    """Load a chat from onecx-chat-svc, propagating ``apm-principal-token``.

    Calls ``GET /internal/chats/{id}`` until chat-svc ships a user-scoped
    ``GET /v1/chats/{chatId}`` (onecx/internal-tasks#995). A 404/403 or any
    transport failure is surfaced as ``ChatAccessError`` so the session fails
    closed.
    """

    def __init__(
        self, settings: ChatSettings | None = None, service_auth: httpx.Auth | None = None
    ) -> None:
        self._settings = settings or ChatSettings()
        self._service_auth = service_auth
        self._client: httpx.AsyncClient | None = None

    def set_client(self, client: httpx.AsyncClient) -> None:
        """Inject a client (used by tests to avoid a live network call)."""
        self._client = client

    async def load(self, chat_id: str, apm_principal_token: str) -> Chat:
        client = self._client or httpx.AsyncClient()
        headers = {"apm-principal-token": apm_principal_token}
        try:
            response = await client.get(
                f"{self._settings.base_url}/internal/chats/{chat_id}",
                headers=headers,
                auth=self._service_auth,
            )
        except httpx.HTTPError as exc:
            raise ChatAccessError(f"chat service unreachable: {exc}") from exc
        if response.status_code in (403, 404):
            raise ChatAccessError(f"chat {chat_id!r} not accessible")
        if not response.is_success:
            raise ChatAccessError(f"chat service error: {response.status_code}")
        body: dict[str, Any] = response.json()
        result = _Chat(chat_id=str(body.get("id") or chat_id), topic=str(body.get("topic") or ""))
        if self._client is None:
            await client.aclose()
        return result
