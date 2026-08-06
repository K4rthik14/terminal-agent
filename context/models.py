"""Data contracts for context selection."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from utils.types import MessageList


@dataclass(frozen=True)
class AgentState:
    """Minimal immutable view of session state used by selectors."""

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
