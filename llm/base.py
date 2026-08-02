"""Abstract LLM client interface.

Responsibilities:
- Defines the LLMClient abstract base class with complete() and stream() methods.
- Defines canonical Message, ToolCall, and ToolDefinition dataclasses used
  across the entire system.
- No provider SDK is imported here. Concrete clients implement this interface.
"""

from abc import ABC, abstractmethod
from collections.abc import Iterator
from typing import Any

from utils.types import MessageList, StreamEvent


class LLMClient(ABC):
    @abstractmethod
    def stream(
        self,
        messages: MessageList,
        tool_schemas: list[dict[str, Any]],
    ) -> Iterator[StreamEvent]:
        """Stream a response, yielding StreamEvent objects."""
        ...
