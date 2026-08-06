"""Compatibility facade for state-driven context orchestration."""

from __future__ import annotations

from collections.abc import Iterable

from context.models import AgentState, ContextSelection, ContextState
from context.orchestrator import PromptOrchestrator
from tools.base import Tool


class ContextManager:
    """Builds context through PromptOrchestrator while preserving the old API."""

    def __init__(self, max_messages: int = 24, **orchestrator_options: object) -> None:
        self._orchestrator = PromptOrchestrator(
            max_messages=max_messages,
            **orchestrator_options,
        )

    def build(
        self,
        state: ContextState | AgentState,
        available_tools: Iterable[Tool],
    ) -> ContextSelection:
        """Build a fresh context from compact state or legacy state."""
        return self._orchestrator.build(self._normalize_state(state), available_tools)

    @staticmethod
    def _normalize_state(state: ContextState | AgentState) -> ContextState:
        if isinstance(state, ContextState):
            return state
        messages = [message for message in state.messages if message.get("role") != "system"]
        goal = next(
            (
                str(message.get("content", "")).strip()
                for message in reversed(messages)
                if message.get("role") == "user" and message.get("content")
            ),
            "",
        )
        tool_results = tuple(message for message in messages if message.get("role") == "tool")
        return ContextState(
            goal=goal,
            conversation_tail=messages[-24:],
            recent_tool_results=tool_results[-8:],
            plan_mode=state.plan_mode,
        )
