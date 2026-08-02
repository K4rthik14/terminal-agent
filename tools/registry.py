"""Tool registry and discovery.

Responsibilities:
- Provides ToolRegistry: the single authoritative map of tool name -> Tool instance.
- Tools register themselves by being imported (explicit registration, not magic).
- Exposes get(name), all(), and as_definitions() for sending schemas to the LLM.
- Raises a clear error on duplicate registration or unknown tool lookup.
"""

from tools.base import Tool
from utils.errors import ToolNotFoundError
from utils.types import JsonDict


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Tool already registered: {tool.name!r}")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool:
        if name not in self._tools:
            raise ToolNotFoundError(f"Unknown tool: {name!r}")
        return self._tools[name]

    def all(self) -> list[Tool]:
        return list(self._tools.values())

    def as_definitions(self) -> list[JsonDict]:
        """Return all tool schemas for sending to the LLM."""
        return [t.to_schema() for t in self._tools.values()]
