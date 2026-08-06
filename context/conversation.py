"""Conversation selection from compact context state."""

from __future__ import annotations

from context.models import ContextState
from utils.types import MessageList


class ConversationSelector:
    """Returns the already-bounded conversation tail from context state."""

    def __init__(self, max_messages: int = 24) -> None:
        self._max_messages = max_messages

    def select(self, state: ContextState) -> MessageList:
        """Return only the recent messages required for the current turn."""
        return list(state.conversation_tail[-self._max_messages :])
