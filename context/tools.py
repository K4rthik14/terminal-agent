"""Relevant tool selection."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from context.models import AgentState
from tools.base import Tool


class RelevantToolSelector:
    """Selects likely tools from the goal while retaining safe session tools."""

    _KEYWORDS: dict[str, tuple[str, ...]] = {
        "read_file": ("read", "inspect", "look at", "summarize", "show", "check"),
        "write_file": ("create", "write", "generate", "scaffold"),
        "edit_file": ("edit", "change", "modify", "update", "fix", "replace"),
        "bash": ("run", "execute", "test", "pytest", "command", "shell", "install"),
        "todo_write": ("plan", "steps", "task", "todo"),
        "web_search": ("search", "research", "latest", "documentation", "news"),
        "web_fetch": ("fetch", "url", "website", "page", "docs"),
        "task": ("delegate", "sub-agent", "parallel"),
    }

    def select(self, goal: str, tools: Iterable[Tool], state: AgentState) -> list[Tool]:
        """Return tools relevant to the current goal in registry order."""
        haystack = " ".join(
            [goal.lower()]
            + [str(message.get("content", "")).lower() for message in state.messages[-4:]]
        )
        available = list(tools)
        selected_names = {
            name for name, keywords in self._KEYWORDS.items() if any(word in haystack for word in keywords)
        }

        # These tools are safe defaults for coding tasks and task tracking.
        if not selected_names:
            selected_names.update({"read_file", "write_file", "edit_file", "bash", "todo_write"})
        else:
            selected_names.add("read_file")

        selected = [tool for tool in available if tool.name in selected_names]
        return selected or available

    @staticmethod
    def schemas(tools: Iterable[Tool]) -> list[dict[str, Any]]:
        """Convert selected tools to provider-neutral function schemas."""
        return [tool.to_schema() for tool in tools]
