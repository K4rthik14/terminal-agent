"""Data contracts for state-driven context selection."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from utils.types import MessageList


@dataclass(frozen=True)
class ContextState:
    """Compact state required to rebuild context for one model iteration.

    This intentionally excludes the full session history. ``conversation_tail``
    contains only the bounded message sequence needed to preserve the current
    tool turn and recent user-visible context.
    """

    goal: str = ""
    conversation_tail: MessageList = field(default_factory=list)
    active_files: tuple[str, ...] = ()
    recent_tool_results: tuple[dict[str, Any], ...] = ()
    plan_mode: bool = False
    iteration: int = 0


@dataclass(frozen=True)
class AgentState:
    """Backward-compatible legacy state accepted by ContextManager."""

    messages: MessageList
    plan_mode: bool = False


@dataclass(frozen=True)
class ContextSelection:
    """Fresh model input assembled for one LLM request."""

    messages: MessageList
    tool_schemas: list[dict[str, Any]]
    goal: str
    relevant_files: list[str] = field(default_factory=list)
    selected_tools: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ContextEvaluation:
    """Lightweight diagnostics for a selected model context."""

    message_count: int
    tool_count: int
    character_count: int
    has_goal: bool
    warnings: tuple[str, ...] = ()
