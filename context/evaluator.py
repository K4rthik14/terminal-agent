"""Evaluation of selected context quality."""

from __future__ import annotations

from context.models import ContextEvaluation, ContextSelection
from context.window import MessageWindow


class ContextEvaluator:
    """Produces diagnostics without changing the selected context."""

    def __init__(self, max_messages: int = 24, max_characters: int = 30_000) -> None:
        self._max_messages = max_messages
        self._max_characters = max_characters

    def evaluate(self, selection: ContextSelection) -> ContextEvaluation:
        """Measure size and basic completeness of one context selection."""
        character_count = MessageWindow.estimate_characters(selection.messages)
        warnings: list[str] = []
        if len(selection.messages) > self._max_messages + 1:
            warnings.append("context exceeds configured message window")
        if character_count > self._max_characters:
            warnings.append("context exceeds configured character budget")
        if not selection.goal:
            warnings.append("context has no active goal")
        if not selection.tool_schemas:
            warnings.append("context has no available tools")
        return ContextEvaluation(
            message_count=len(selection.messages),
            tool_count=len(selection.tool_schemas),
            character_count=character_count,
            has_goal=bool(selection.goal),
            warnings=tuple(warnings),
        )
