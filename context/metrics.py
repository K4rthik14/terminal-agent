"""Execution metrics and results for agent runs."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import StrEnum


class AgentRunStatus(StrEnum):
    """Terminal statuses the current runtime can genuinely distinguish.

    The runtime can distinguish a completed reply, an LLM failure, and a run
    stopped by an execution budget. It cannot distinguish tool-error, cancelled,
    or verification-only outcomes as terminal states, so those are not modeled.
    """

    SUCCESS = "success"
    LLM_ERROR = "llm_error"
    BUDGET_EXCEEDED = "budget_exceeded"
    ERROR = "error"  # run ended unsuccessfully without a recorded cause


@dataclass
class AgentRunResult:
    """Structured outcome of one Agent.run() call.

    Callers must never need to parse output text to learn whether a run failed:
    ``success``/``error``/``status`` carry that information explicitly.
    """

    output: str
    success: bool
    error: str | None
    metrics: AgentRunMetrics
    status: AgentRunStatus


@dataclass
class AgentRunMetrics:
    """Useful, low-cost metrics collected during one agent run."""

    success: bool = False
    execution_time: float = 0.0
    tool_usage: dict[str, int] = field(default_factory=dict)
    tool_calls: int = 0
    budget_exceeded: bool = False
    budget_exceeded_reason: str | None = None
    loop_detection_events: int = 0
    context_message_counts: list[int] = field(default_factory=list)
    context_character_counts: list[int] = field(default_factory=list)
    context_tool_counts: list[int] = field(default_factory=list)
    verification_attempts: int = 0
    verification_passes: int = 0
    verification_failures: int = 0
    verification_errors: int = 0
    rlm_enabled: bool = False
    rlm_iterations: int = 0
    rlm_tool_calls: int = 0
    rlm_brief_chars: int = 0
    rlm_degraded: bool = False
    _started_at: float = field(default_factory=time.monotonic, repr=False)

    def finish(self, success: bool) -> None:
        """Finalize elapsed time and run outcome."""
        self.success = success
        self.execution_time = time.monotonic() - self._started_at

    def record_tool(self, name: str) -> None:
        """Record one attempted tool execution."""
        self.tool_usage[name] = self.tool_usage.get(name, 0) + 1
        self.tool_calls += 1

    def mark_budget_exceeded(self, reason: str) -> None:
        """Record that an execution budget stopped the run."""
        self.budget_exceeded = True
        self.budget_exceeded_reason = reason

    def record_context(self, message_count: int, character_count: int, tool_count: int) -> None:
        """Record the size of one context sent to the model."""
        self.context_message_counts.append(message_count)
        self.context_character_counts.append(character_count)
        self.context_tool_counts.append(tool_count)

    def record_verification(self, passed: bool, error: bool = False) -> None:
        """Record one deterministic verification attempt."""
        self.verification_attempts += 1
        if passed:
            self.verification_passes += 1
        else:
            self.verification_failures += 1
        if error:
            self.verification_errors += 1
