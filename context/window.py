"""Token-conscious conversation window selection."""

from __future__ import annotations

from typing import Any

from utils.types import MessageList


class MessageWindow:
    """Selects recent messages while preserving tool-call message groups."""

    def __init__(self, max_messages: int = 24) -> None:
        if max_messages < 4:
            raise ValueError("max_messages must be at least 4")
        self._max_messages = max_messages

    def select(self, messages: MessageList) -> MessageList:
        """Return system context plus the newest complete conversation window."""
        if len(messages) <= self._max_messages:
            return list(messages)

        system = [message for message in messages if message.get("role") == "system"][:1]
        conversation = [message for message in messages if message.get("role") != "system"]
        selected = conversation[-self._max_messages :]

        # A tool result is only meaningful with its preceding assistant tool call.
        # Include that assistant message when trimming starts inside a tool turn.
        if selected and selected[0].get("role") == "tool":
            start = conversation.index(selected[0])
            if start > 0:
                selected.insert(0, conversation[start - 1])

        return system + selected

    @staticmethod
    def estimate_characters(messages: list[dict[str, Any]]) -> int:
        """Return a cheap size estimate for diagnostics without tokenization."""
        return sum(len(str(message.get("content", ""))) for message in messages)
