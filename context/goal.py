"""Current-task goal extraction."""

from __future__ import annotations

from context.models import ContextState


class GoalExtractor:
    """Extracts the active goal from compact context state."""

    def extract(self, state: ContextState) -> str:
        """Return the current goal without scanning the full session history."""
        return state.goal.strip()
