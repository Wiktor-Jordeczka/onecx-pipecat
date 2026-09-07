"""Conversation persistence: append + list durable voice entries."""

from __future__ import annotations

from typing import Protocol

from onecx_pipecat.config import PersistenceSettings
from onecx_pipecat.models import VoiceEntry


class ConversationPersistence(Protocol):
    async def append(self, session_id: str, entry: VoiceEntry) -> str: ...
    async def list_entries(self, session_id: str) -> list[VoiceEntry]: ...
    async def get(self, session_id: str, entry_id: str) -> VoiceEntry | None: ...


class InMemoryPersistence:
    """Process-local storage; sufficient for the foundation and CI."""

    def __init__(self, settings: PersistenceSettings | None = None) -> None:
        self._settings = settings or PersistenceSettings()
        self._sessions: dict[str, dict[str, VoiceEntry]] = {}

    async def append(self, session_id: str, entry: VoiceEntry) -> str:
        store = self._sessions.setdefault(session_id, {})
        entry_id = f"{session_id}:{len(store) + 1}"
        store[entry_id] = entry
        return entry_id

    async def list_entries(self, session_id: str) -> list[VoiceEntry]:
        return list(self._sessions.get(session_id, {}).values())

    async def get(self, session_id: str, entry_id: str) -> VoiceEntry | None:
        return self._sessions.get(session_id, {}).get(entry_id)
