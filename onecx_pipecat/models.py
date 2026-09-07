"""Typed domain value models for the Pipecat foundation.

State names mirror the vocabulary in
``prototypes/voice-turn-sequence-prototype.html`` so the eventual session
logic can use the same strings without translation.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class Principal(BaseModel):
    """An authenticated actor bound to a voice session."""

    subject: str
    tenant_id: str
    roles: list[str] = Field(default_factory=list)


class AgentConfigSnapshot(BaseModel):
    """A pinned agent configuration version for one run."""

    agent_id: str
    version: int
    system_prompt: str = ""
    tool_names: list[str] = Field(default_factory=list)


class VoiceEntryKind(StrEnum):
    HUMAN = "HUMAN"
    ASSISTANT = "ASSISTANT"
    ASSISTANT_CHECKPOINT = "ASSISTANT_CHECKPOINT"
    TOOL_PROPOSAL = "TOOL_PROPOSAL"
    TOOL_DECISION = "TOOL_DECISION"
    TOOL_RESULT = "TOOL_RESULT"


class VoiceEntry(BaseModel):
    """A durable conversation entry (visible or hidden checkpoint)."""

    kind: VoiceEntryKind
    text: str
    hidden: bool = False
    idempotency_key: str | None = None


class PermissionAction(StrEnum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    ALWAYS_ASK = "ALWAYS_ASK"


class PermissionDecision(BaseModel):
    """The result of a permission evaluation for a tool call."""

    action: PermissionAction
    reason: str = ""


class PermissionDecisionStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    DENIED = "DENIED"
    CONSUMED = "CONSUMED"


class ToolProposal(BaseModel):
    """A protected tool call awaiting a permission decision."""

    proposal_id: str
    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    status: PermissionDecisionStatus = PermissionDecisionStatus.PENDING
    reason: str = ""


class TranscriptState(StrEnum):
    NONE = "NONE"
    PARTIAL = "PARTIAL"
    FINAL = "FINAL"
    FAILED = "FAILED"


class AudioState(StrEnum):
    NONE = "NONE"
    SYNTHESIZING = "SYNTHESIZING"
    PLAYING = "PLAYING"
    STOPPED = "STOPPED"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"
