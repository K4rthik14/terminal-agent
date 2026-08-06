"""Execution metrics for agent runs."""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class AgentRunMetrics:
    """Useful, low-cost metrics collected during one agent run."""

    success: bool = False
    execution_time: float = 0.0
    tool_usage: dict[str, int] = field(default_factory=dict)
    loop_detection_events: int = 0
    context_message_counts: list[int] = field(default_factory=list)
    context_character_counts: list[int] = field(default_factory=list)
    context_tool_counts: list[int] = field(default_factory=list)
    _started_at: float = field(default_factory=time.monotonic, repr=False)

    def finish(self, success: bool) -> None:
        """Finalize elapsed time and run outcome."""
        self.success = success
        self.execution_time = time.monotonic() - self._started_at

    def record_tool(self, name: str) -> None:
        """Record one attempted tool execution."""
        self.tool_usage[name] = self.tool_usage.get(name, 0) + 1

    def record_context(self, message_count: int, character_count: int, tool_count: int) -> None:
        """Record the size of one context sent to the model."""
        self.context_message_counts.append(message_count)
        self.context_character_counts.append(character_count)
        self.context_tool_counts.append(tool_count)
