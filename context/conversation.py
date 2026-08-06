"""Conversation selection for one model request."""

from __future__ import annotations

from context.models import AgentState
from context.window import MessageWindow
from utils.types import MessageList


class ConversationSelector:
    """Selects recent conversation messages without owning session state."""

    def __init__(self, max_messages: int = 24) -> None:
        self._window = MessageWindow(max_messages)

    def select(self, state: AgentState) -> MessageList:
        """Return a bounded recent conversation, excluding stale system prompts."""
        messages = [message for message in state.messages if message.get("role") != "system"]
        return self._window.select(messages)
