"""Current-task goal extraction."""

from __future__ import annotations

from context.models import AgentState


class GoalExtractor:
    """Extracts the latest user request as the active task goal."""

    def extract(self, state: AgentState) -> str:
        """Return the newest non-empty user message."""
        for message in reversed(state.messages):
            if message.get("role") == "user" and message.get("content"):
                return str(message["content"]).strip()
        return ""
