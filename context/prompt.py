"""Prompt assembly for selected context."""

from __future__ import annotations

from context.builder import ContextBuilder
from context.models import AgentState
from utils.types import MessageList


class PromptBuilder:
    """Builds a fresh system message from the selected task state."""

    def __init__(self, builder: ContextBuilder | None = None) -> None:
        self._builder = builder or ContextBuilder()

    def build_system_message(
        self,
        goal: str,
        relevant_files: list[str],
        state: AgentState,
    ) -> dict[str, str]:
        """Return a new system message for the current request."""
        sections = [self._builder.build_system_prompt()]
        if goal:
            sections.append(f"Current task:\n{goal}")
        if relevant_files:
            sections.append("Relevant file hints:\n" + "\n".join(f"- {path}" for path in relevant_files))
        if state.plan_mode:
            sections.append("Planning mode is enabled. Do not execute write tools.")
        return {"role": "system", "content": "\n\n".join(sections)}

    @staticmethod
    def assemble(system_message: dict[str, str], conversation: MessageList) -> MessageList:
        """Place the fresh system message before the selected conversation."""
        return [system_message, *conversation]
