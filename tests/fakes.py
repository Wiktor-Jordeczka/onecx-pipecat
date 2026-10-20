"""Test doubles for the OneCX boundaries; production code ships only real adapters."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Mapping
from types import SimpleNamespace
from typing import Any

from onecx_pipecat.adapters.agent_config import AgentConfigError
from onecx_pipecat.adapters.auth import AuthenticationError
from onecx_pipecat.adapters.chat import ChatAccessError
from onecx_pipecat.adapters.mcp import McpDiscovery, McpToolResult
from onecx_pipecat.config import Settings
from onecx_pipecat.container import AppContainer
from onecx_pipecat.models import (
    AgentConfigSnapshot,
    AgentToolSnapshot,
    McpServerSnapshot,
    Principal,
    ToolProposal,
    VoiceEntry,
)


class FakeAuth:
    def __init__(self) -> None:
        self._principals: dict[str, Principal] = {}
        self._expired: set[str] = set()

    def seed(
        self, token: str, subject: str, tenant_id: str, roles: list[str] | None = None
    ) -> None:
        self._principals[token] = Principal(
            subject=subject, tenant_id=tenant_id, roles=list(roles or [])
        )

    def mark_expired(self, token: str) -> None:
        self._expired.add(token)

    async def authenticate(self, token: str) -> Principal:
        if token not in self._principals or token in self._expired:
            raise AuthenticationError("unknown or expired token")
        return self._principals[token]

    def is_expired(self, token: str) -> bool:
        return token not in self._principals or token in self._expired

    async def refresh(self, token: str) -> Principal:
        return await self.authenticate(token)

    async def service_token(self) -> str:
        return "svc"


class FakeChat:
    def __init__(self) -> None:
        self._topics: dict[str, str] = {}
        self._users: dict[str, frozenset[str]] = {}

    def register(self, chat_id: str, topic: str = "", users: tuple[str, ...] = ("user-1",)) -> None:
        self._topics[chat_id] = topic
        self._users[chat_id] = frozenset(users)

    async def load(self, chat_id: str, apm_principal_token: str):
        if chat_id not in self._topics:
            raise ChatAccessError(f"chat {chat_id!r} not accessible")
        return SimpleNamespace(
            chat_id=chat_id, topic=self._topics[chat_id], user_ids=self._users[chat_id]
        )


class FakeAgentConfig:
    def __init__(self) -> None:
        self._snapshots: dict[str, AgentConfigSnapshot] = {}

    def register(self, snapshot: AgentConfigSnapshot) -> None:
        self._snapshots[snapshot.agent_id] = snapshot

    async def pin(self, tenant_id: str, agent_id: str, apm_principal_token: str):
        if agent_id not in self._snapshots:
            raise AgentConfigError(f"no configuration for agent={agent_id}")
        return self._snapshots[agent_id]


class FakePermission:
    def __init__(self) -> None:
        self._denied: set[str] = set()

    def deny_voice(self, subject: str) -> None:
        self._denied.add(subject)

    async def has_voice_permission(self, principal: Principal, apm_principal_token: str) -> bool:
        return principal.subject not in self._denied


class FakeMcp:
    """Reports the tools/failures seeded per server, recording what discovery was asked."""

    def __init__(self) -> None:
        self.tools: dict[str, list[str]] = {}
        self.failures: dict[str, str] = {}
        self.calls: list[tuple[list[str], dict[str, str]]] = []
        self.invocations: list[tuple[str, str, dict[str, str]]] = []

    async def discover(
        self, servers: list[McpServerSnapshot], headers: Mapping[str, str]
    ) -> McpDiscovery:
        self.calls.append(([s.name for s in servers], dict(headers)))
        discovery = McpDiscovery()
        for server in servers:
            if server.name in self.failures:
                discovery.degraded.append((server.name, self.failures[server.name]))
                continue
            for name in self.tools.get(server.name, []):
                discovery.tools.append(
                    AgentToolSnapshot(
                        tool_name=name, server_name=server.name, server_url=server.url
                    )
                )
        return discovery

    async def invoke(
        self,
        server: McpServerSnapshot,
        proposal: ToolProposal,
        headers: Mapping[str, str],
        args: dict[str, Any] | None = None,
    ) -> McpToolResult:
        self.invocations.append((server.name, proposal.tool_name, dict(headers)))
        return McpToolResult(ok=True, value="done")


def fake_container(
    *, token: str = "tok-user", chat_id: str = "chat-1", agent_id: str = "onecx-agent"
) -> AppContainer:
    """An app container with fakes for every OneCX boundary and one usable user/chat/agent."""
    container = AppContainer(Settings())
    auth, chat, agent_config = FakeAuth(), FakeChat(), FakeAgentConfig()
    auth.seed(token, subject="user-1", tenant_id="local", roles=["voice"])
    chat.register(chat_id, topic="general")
    agent_config.register(
        AgentConfigSnapshot(agent_id=agent_id, schema_version="1", system_prompt="be brief")
    )
    container.auth = auth
    container.chat = chat
    container.agent_config = agent_config
    container.permission = FakePermission()
    container.mcp = FakeMcp()
    return container


# --- controlled streaming speech doubles + event collector -----------------
#
# These drive the *streaming* speech adapters behind a ``VoiceTurn`` (partial/
# final transcripts, incremental audio, barge-in, and injected failures). The
# ``sleep`` yields let a concurrent barge-in land mid-stream.


class FakeStt:
    """Yields ``(text, is_final)`` transcript frames for a controlled stream."""

    def __init__(
        self,
        frames: list[tuple[str, bool]] | None = None,
        *,
        sleep: float = 0.0,
        fail: bool = False,
    ) -> None:
        self.frames = frames if frames is not None else [("hello", False), ("hello world", True)]
        self.sleep = sleep
        self.fail = fail

    def stream(self, audio_bytes: bytes) -> AsyncIterator[tuple[str, bool]]:
        async def _stream():
            if not audio_bytes:
                return
            if self.fail:
                raise RuntimeError("stt boom")
            for text, is_final in self.frames:
                if self.sleep:
                    await asyncio.sleep(self.sleep)
                yield text, is_final

        return _stream()


class FakeTts:
    """Yields audio chunks for a controlled stream."""

    def __init__(
        self,
        chunks: list[bytes] | None = None,
        *,
        sleep: float = 0.0,
        fail: bool = False,
    ) -> None:
        self.chunks = chunks if chunks is not None else [b"a", b"b", b"c"]
        self.sleep = sleep
        self.fail = fail

    def stream(self, text: str) -> AsyncIterator[bytes]:
        async def _stream():
            if not text:
                return
            if self.fail:
                raise RuntimeError("tts boom")
            for chunk in self.chunks:
                if self.sleep:
                    await asyncio.sleep(self.sleep)
                yield chunk

        return _stream()


class FakePersistence:
    """A recording persistence that can be made to fail on the human/assistant write."""

    def __init__(self, *, fail_human: bool = False, fail_assistant: bool = False) -> None:
        self.entries: list[VoiceEntry] = []
        self.fail_human = fail_human
        self.fail_assistant = fail_assistant

    async def append(self, session_id: str, entry: VoiceEntry) -> str:
        if (entry.kind.value == "HUMAN" and self.fail_human) or (
            entry.kind.value == "ASSISTANT" and self.fail_assistant
        ):
            raise RuntimeError("persistence boom")
        entry_id = f"{session_id}:{len(self.entries) + 1}"
        self.entries.append(entry)
        return entry_id

    async def list_entries(self, session_id: str) -> list[VoiceEntry]:
        return list(self.entries)


class Collector:
    """Collects the events a turn streams through its sink, in order."""

    def __init__(self) -> None:
        self.events: list[Any] = []

    def __call__(self, event: Any) -> None:
        self.events.append(event)

    @property
    def kinds(self) -> list[str]:
        return [e.kind for e in self.events]
