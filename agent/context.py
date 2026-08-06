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
from context.manager import ContextManager
from context.models import ContextSelection, ContextState
from context.window import MessageWindow
from tools.base import Tool
from utils.types import MessageList


@dataclass
class AgentContext:
    """All mutable state for one agent session."""

    messages: MessageList = field(default_factory=list)
    plan_mode: bool = False
    auto_approve: bool = False
    max_context_messages: int = 24
    iteration: int = 0
    _builder: ContextBuilder = field(default_factory=ContextBuilder, repr=False)
    _window: MessageWindow = field(init=False, repr=False)
    _manager: ContextManager = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._window = MessageWindow(self.max_context_messages)
        self._manager = ContextManager(max_messages=self.max_context_messages)

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
        """Return a bounded context for compatibility with older callers."""
        return self._window.select(self.messages)

    def select_context(self, tools: list[Tool]) -> ContextSelection:
        """Build fresh messages and selected tools from compact current state."""
        conversation = [
            message for message in self.messages if message.get("role") != "system"
        ]
        conversation_tail = self._window.select(conversation)
        goal = next(
            (
                str(message.get("content", "")).strip()
                for message in reversed(conversation_tail)
                if message.get("role") == "user" and message.get("content")
            ),
            "",
        )
        state = ContextState(
            goal=goal,
            conversation_tail=conversation_tail,
            recent_tool_results=tuple(
                message for message in conversation_tail if message.get("role") == "tool"
            ),
            plan_mode=self.plan_mode,
            iteration=self.iteration,
        )
        self.iteration += 1
        return self._manager.build(state, tools)

    def init_system_message(self) -> None:
        """Prepend the system message once at session start."""
        if not self.messages or self.messages[0].get("role") != "system":
            self.messages.insert(0, {"role": "system", "content": self.system_prompt()})
