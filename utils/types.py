"""Shared type aliases and dataclasses.

Responsibilities:
- Single source of truth for all data shapes that cross module boundaries.
- Defines: Message, ToolCall, ToolResult, Plan, PlanStep, ApprovalDecision,
  StreamEvent, and common type aliases (MessageList, ToolName, etc.).
- Pure data definitions only. No methods with business logic.
- Imported by llm/, tools/, agent/, and cli/ — never imports from them.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

# Type aliases
MessageList = list[dict[str, Any]]
ToolName = str
JsonDict = dict[str, Any]


class ApprovalMode(str, Enum):
    ALWAYS = "always"
    NEVER = "never"
    AUTO = "auto"   # only prompt for non-read-only tools


class ApprovalDecision(str, Enum):
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: str = ""   # raw JSON string, accumulated from stream deltas


@dataclass
class ToolResult:
    tool_call_id: str
    content: str
    is_error: bool = False


@dataclass
class StreamEvent:
    # type is one of: "token" | "tool_call_delta" | "done"
    type: str
    content: str = ""
    tool_call_index: int = 0
    tool_call_id: str = ""
    tool_call_name: str = ""
    finish_reason: str | None = None
