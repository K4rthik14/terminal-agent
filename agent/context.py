"""Agent session state and context projection.

Responsibilities:
- Carries mutable state for one agent session.
- Owns message history and session flags.
- Delegates system-prompt construction and conversation-window selection.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from context.builder import ContextBuilder
from context.window import MessageWindow
from utils.types import MessageList


@dataclass
class AgentContext:
    """All mutable state for one agent session."""

    messages: MessageList = field(default_factory=list)
    plan_mode: bool = False
    auto_approve: bool = False
    max_context_messages: int = 24
    _builder: ContextBuilder = field(default_factory=ContextBuilder, repr=False)
    _window: MessageWindow = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._window = MessageWindow(self.max_context_messages)

    def add_user_message(self, content: str) -> None:
        self.messages.append({"role": "user", "content": content})

    def add_assistant_message(
        self,
        content: str,
        tool_calls: list[dict[str, Any]] | None = None,
    ) -> None:
        message: dict[str, Any] = {"role": "assistant", "content": content}
        if tool_calls:
            message["tool_calls"] = tool_calls
        self.messages.append(message)

    def add_tool_result(self, tool_call_id: str, content: str) -> None:
        self.messages.append({"role": "tool", "tool_call_id": tool_call_id, "content": content})

    def system_prompt(self) -> str:
        """Build the stable system context from reusable prompt sources."""
        return self._builder.build_system_prompt()

    def messages_for_llm(self) -> MessageList:
        """Return only the relevant bounded context for the next model call."""
        return self._window.select(self.messages)

    def init_system_message(self) -> None:
        """Prepend the system message once at session start."""
        if not self.messages or self.messages[0].get("role") != "system":
            self.messages.insert(0, {"role": "system", "content": self.system_prompt()})
