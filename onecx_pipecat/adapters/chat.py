"""Chat adapter: load a chat by id as the user.

A voice session starts against an existing chat; loading it as the user (the
``apm-principal-token`` is propagated so the call acts on the user's behalf)
is the first eligibility check. A missing or forbidden chat is a typed
``ChatAccessError`` so the session can fail closed. The internal endpoint is
authorized by Pipecat's service token, so the returned chat carries its owner
and participants and the session checks the user against them.
"""

from __future__ import annotations

from typing import Any, Protocol
from urllib.parse import quote

import httpx

from onecx_pipecat.config import ChatSettings


class ChatAccessError(Exception):
    """Raised when the requested chat is missing, forbidden, or the service is
    unreachable — i.e. the user may not voice in this chat."""


class Chat(Protocol):
    """The chat a voice session is anchored to."""

    chat_id: str
    topic: str
    # The chat owner and participants; the session requires the user to be one of them.
    user_ids: frozenset[str]


class _Chat:
    """The subset of the onecx-chat-svc ``Chat`` record a session needs."""

    def __init__(
        self, chat_id: str, topic: str = "", user_ids: frozenset[str] = frozenset()
    ) -> None:
        self.chat_id = chat_id
        self.topic = topic
        self.user_ids = user_ids


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
            try:
                response = await client.get(
                    f"{self._settings.base_url}/internal/chats/{quote(chat_id, safe='')}",
                    headers=headers,
                    auth=self._service_auth,
                )
            except httpx.HTTPError as exc:
                raise ChatAccessError(f"chat service unreachable: {exc}") from exc
            if response.status_code in (403, 404):
                raise ChatAccessError(f"chat {chat_id!r} not accessible")
            if not response.is_success:
                raise ChatAccessError(f"chat service error: {response.status_code}")
            try:
                body = response.json()
            except ValueError as exc:
                raise ChatAccessError("chat service returned a malformed response") from exc
            return _parse_chat(body, chat_id)
        finally:
            if client is not self._client:
                await client.aclose()


def _parse_chat(body: Any, chat_id: str) -> Chat:
    if not isinstance(body, dict):
        raise ChatAccessError("chat service returned a malformed response")
    user_ids: set[str] = set()
    if owner := body.get("userId"):
        user_ids.add(str(owner))
    participants = body.get("participants") or []
    if not isinstance(participants, list):
        raise ChatAccessError("chat service returned a malformed response")
    for participant in participants:
        if isinstance(participant, dict) and participant.get("userId"):
            user_ids.add(str(participant["userId"]))
    return _Chat(
        chat_id=str(body.get("id") or chat_id),
        topic=str(body.get("topic") or ""),
        user_ids=frozenset(user_ids),
    )
