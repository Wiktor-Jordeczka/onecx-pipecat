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
    """Process-local storage; sufficient for the foundation and CI.

    Enforces ``persistence.max_entries_per_session``: when a session exceeds
    the cap the oldest entry is evicted so the per-session store stays within
    the configured soft limit.
    """

    def __init__(self, settings: PersistenceSettings | None = None) -> None:
        self._settings = settings or PersistenceSettings()
        self._sessions: dict[str, dict[str, VoiceEntry]] = {}
        self._sequence: dict[str, int] = {}

    async def append(self, session_id: str, entry: VoiceEntry) -> str:
        store = self._sessions.setdefault(session_id, {})
        self._sequence[session_id] = self._sequence.get(session_id, 0) + 1
        entry_id = f"{session_id}:{self._sequence[session_id]}"
        store[entry_id] = entry
        # Keep the store within the configured cap by evicting the oldest
        # entry when it is exceeded. The store only ever gains new unique
        # keys, so its insertion order is chronological and the first key is
        # the oldest entry.
        while len(store) > self._settings.max_entries_per_session:
            del store[next(iter(store))]
        return entry_id

    async def list_entries(self, session_id: str) -> list[VoiceEntry]:
        return list(self._sessions.get(session_id, {}).values())

    async def get(self, session_id: str, entry_id: str) -> VoiceEntry | None:
        return self._sessions.get(session_id, {}).get(entry_id)
