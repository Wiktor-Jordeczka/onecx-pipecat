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
    title: str


class _Chat:
    """Concrete stand-in for the chat record returned by onecx-chat-svc."""

    def __init__(self, chat_id: str, title: str = "") -> None:
        self.chat_id = chat_id
        self.title = title


class ChatAdapter(Protocol):
    """Replaceable onecx-chat-svc boundary."""

    async def load(self, chat_id: str, apm_principal_token: str) -> Chat: ...


class InMemoryChatAdapter:
    """Deterministic chat table for local runs and tests."""

    def __init__(self, settings: ChatSettings | None = None) -> None:
        self._settings = settings or ChatSettings()
        self._table: dict[str, Chat] = {}

    def register(self, chat_id: str, title: str = "") -> None:
        self._table[chat_id] = _Chat(chat_id=chat_id, title=title)

    async def load(self, chat_id: str, apm_principal_token: str) -> Chat:
        chat = self._table.get(chat_id)
        if chat is None:
            raise ChatAccessError(f"chat {chat_id!r} not found or not accessible")
        return chat


class HttpChatAdapter:
    """Load a chat from onecx-chat-svc, propagating ``apm-principal-token``.

    A 404/403 or any transport failure is surfaced as ``ChatAccessError`` so
    the session fails closed without distinguishing between "not found" and
    "forbidden" (both mean "no voice here").
    """

    def __init__(self, settings: ChatSettings | None = None) -> None:
        self._settings = settings or ChatSettings()
        self._client: httpx.AsyncClient | None = None

    def set_client(self, client: httpx.AsyncClient) -> None:
        """Inject a client (used by tests to avoid a live network call)."""
        self._client = client

    async def load(self, chat_id: str, apm_principal_token: str) -> Chat:
        client = self._client or httpx.AsyncClient()
        headers = {"apm-principal-token": apm_principal_token}
        try:
            response = await client.get(
                f"{self._settings.base_url}/v1/chats/{chat_id}", headers=headers
            )
        except httpx.HTTPError as exc:
            raise ChatAccessError(f"chat service unreachable: {exc}") from exc
        if response.status_code in (403, 404):
            raise ChatAccessError(f"chat {chat_id!r} not accessible")
        if not response.is_success:
            raise ChatAccessError(f"chat service error: {response.status_code}")
        body: dict[str, Any] = response.json()
        result = _Chat(chat_id=chat_id, title=body.get("title", ""))
        if self._client is None:
            await client.aclose()
        return result
