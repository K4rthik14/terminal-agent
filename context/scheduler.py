"""Per-iteration tool scheduling."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from context.models import ContextState
from context.tools import RelevantToolSelector
from tools.base import Tool


class ToolScheduler:
    """Exposes only tools relevant to the current task and execution state."""

    def __init__(self, selector: RelevantToolSelector | None = None) -> None:
        self._selector = selector or RelevantToolSelector()

    def schedule(self, state: ContextState, available_tools: Iterable[Tool]) -> list[Tool]:
        """Return the tools available for the current LLM iteration."""
        return self._selector.select(state, available_tools)

    def schemas(
        self,
        state: ContextState,
        available_tools: Iterable[Tool],
    ) -> list[dict[str, Any]]:
        """Return provider-neutral schemas for scheduled tools."""
        return self._selector.schemas(self.schedule(state, available_tools))
