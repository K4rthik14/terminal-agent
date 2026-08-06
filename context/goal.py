"""Current-task goal extraction."""

from __future__ import annotations

from context.models import ContextState


class GoalExtractor:
    """Extracts and normalizes the active user objective from compact state."""

    def __init__(self, max_length: int = 240) -> None:
        if max_length < 1:
            raise ValueError("max_length must be positive")
        self._max_length = max_length

    def extract(self, state: ContextState) -> str:
        """Return a concise current goal without scanning full session history."""
        goal = state.goal.strip()
        if not goal:
            goal = self._latest_user_message(state)
        return self._compact(goal)

    def _latest_user_message(self, state: ContextState) -> str:
        for message in reversed(state.conversation_tail):
            if message.get("role") == "user" and message.get("content"):
                return str(message["content"])
        return ""

    def _compact(self, value: str) -> str:
        normalized = " ".join(value.split())
        if len(normalized) <= self._max_length:
            return normalized
        return normalized[: self._max_length - 1].rstrip() + "…"
