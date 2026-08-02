"""Abstract Tool interface.

Responsibilities:
- Defines the Tool abstract base class that every tool must implement.
- Requires: name (str), description (str), parameters (JSON Schema dict),
  and run(input) -> ToolResult.
- Tools are self-describing: they carry everything the LLM needs to call them.
"""

from abc import ABC, abstractmethod
from typing import Any

from utils.types import ToolResult


class Tool(ABC):
    name: str = ""
    description: str = ""
    parameters: dict[str, Any] = {}
    is_read_only: bool = False  # False = requires human approval in AUTO mode

    @abstractmethod
    def run(self, args: dict[str, Any]) -> ToolResult:
        """Execute the tool. Must return a ToolResult. Never raise — catch internally."""
        ...

    def to_schema(self) -> dict[str, Any]:
        """Return the OpenAI function-calling JSON schema for this tool."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }
