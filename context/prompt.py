"""Prompt assembly for selected context."""

from __future__ import annotations

from context.builder import ContextBuilder
from context.models import ContextState
from tools.base import Tool
from utils.types import MessageList

_TOOL_LIMITATIONS = {
    "write_file": "does not create missing parent directories",
    "edit_file": "requires the target file and exact text to already exist",
    "read_file": "reads files but does not modify them",
}


class PromptBuilder:
    """Builds a fresh system message from the selected task state."""

    def __init__(self, builder: ContextBuilder | None = None) -> None:
        self._builder = builder or ContextBuilder()

    def build_system_message(
        self,
        goal: str,
        relevant_files: list[str],
        state: ContextState,
        available_tools: list[Tool] | None = None,
    ) -> dict[str, str]:
        """Return a new system message for the current request."""
        sections = [self._builder.build_system_prompt()]
        if goal:
            sections.append(f"Current task:\n{goal}")
        if relevant_files:
            sections.append(
                "Relevant file hints:\n" + "\n".join(f"- {path}" for path in relevant_files)
            )
        if available_tools:
            sections.append(self._available_tools_section(available_tools))
        if state.plan_mode:
            sections.append("Planning mode is enabled. Do not execute write tools.")
        return {"role": "system", "content": "\n\n".join(sections)}

    @staticmethod
    def _available_tools_section(tools: list[Tool]) -> str:
        lines = ["Available tools:"]
        for tool in tools:
            description = tool.description.strip()
            limitation = _TOOL_LIMITATIONS.get(tool.name)
            if limitation:
                description = f"{description}; limitation: {limitation}"
            lines.append(f"- {tool.name} — {description}")
        return "\n".join(lines)

    @staticmethod
    def assemble(system_message: dict[str, str], conversation: MessageList) -> MessageList:
        """Place the fresh system message before the selected conversation."""
        return [system_message, *conversation]
