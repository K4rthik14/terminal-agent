"""Evaluation of selected context quality."""

from __future__ import annotations

from context.models import ContextEvaluation, ContextSelection
from context.window import MessageWindow


class ContextEvaluator:
    """Produces diagnostics without changing the selected context."""

    def __init__(self, max_messages: int = 24, max_characters: int = 30_000) -> None:
        if max_messages < 1:
            raise ValueError("max_messages must be positive")
        if max_characters < 1:
            raise ValueError("max_characters must be positive")
        self._max_messages = max_messages
        self._max_characters = max_characters

    def evaluate(self, selection: ContextSelection) -> ContextEvaluation:
        """Measure size, completeness, and budget usage of one selection."""
        character_count = MessageWindow.estimate_characters(selection.messages)
        message_count = len(selection.messages)
        system_present = bool(selection.messages and selection.messages[0].get("role") == "system")
        tool_names = tuple(
            str(schema.get("function", {}).get("name", ""))
            for schema in selection.tool_schemas
        )
        warnings: list[str] = []
        if message_count > self._max_messages + 1:
            warnings.append("context exceeds configured message window")
        if character_count > self._max_characters:
            warnings.append("context exceeds configured character budget")
        if not selection.goal:
            warnings.append("context has no active goal")
        if not selection.tool_schemas:
            warnings.append("context has no available tools")
        if not system_present:
            warnings.append("context has no leading system message")

        return ContextEvaluation(
            message_count=message_count,
            tool_count=len(selection.tool_schemas),
            character_count=character_count,
            has_goal=bool(selection.goal),
            system_message_present=system_present,
            relevant_file_count=len(selection.relevant_files),
            selected_tool_names=tool_names,
            average_message_characters=character_count / message_count if message_count else 0.0,
            character_budget_utilization=character_count / self._max_characters,
            warnings=tuple(warnings),
        )
