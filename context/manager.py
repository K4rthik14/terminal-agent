"""State-driven context selection pipeline."""

from __future__ import annotations

from collections.abc import Iterable

from context.conversation import ConversationSelector
from context.files import RelevantFileSelector
from context.goal import GoalExtractor
from context.models import AgentState, ContextSelection
from context.prompt import PromptBuilder
from context.tools import RelevantToolSelector
from tools.base import Tool


class ContextManager:
    """Coordinates independent selectors to build one fresh model request."""

    def __init__(
        self,
        max_messages: int = 24,
        goal_extractor: GoalExtractor | None = None,
        file_selector: RelevantFileSelector | None = None,
        tool_selector: RelevantToolSelector | None = None,
        conversation_selector: ConversationSelector | None = None,
        prompt_builder: PromptBuilder | None = None,
    ) -> None:
        self._goals = goal_extractor or GoalExtractor()
        self._files = file_selector or RelevantFileSelector()
        self._tools = tool_selector or RelevantToolSelector()
        self._conversation = conversation_selector or ConversationSelector(max_messages)
        self._prompts = prompt_builder or PromptBuilder()

    def build(self, state: AgentState, available_tools: Iterable[Tool]) -> ContextSelection:
        """Build a fresh, task-focused context from current agent state."""
        tools = list(available_tools)
        goal = self._goals.extract(state)
        relevant_files = self._files.select(goal, state)
        selected_tools = self._tools.select(goal, tools, state)
        conversation = self._conversation.select(state)
        system_message = self._prompts.build_system_message(goal, relevant_files, state)
        messages = self._prompts.assemble(system_message, conversation)
        return ContextSelection(
            messages=messages,
            tool_schemas=self._tools.schemas(selected_tools),
            goal=goal,
            relevant_files=relevant_files,
            selected_tools=[tool.name for tool in selected_tools],
        )
