"""Contracts for local multi-agent orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from context.metrics import AgentRunMetrics
from context.models import ContextState


class AgentRole(StrEnum):
    """Specialized responsibilities available to the coordinator."""

    PLANNER = "planner"
    EXECUTOR = "executor"
    REVIEWER = "reviewer"
    RESEARCHER = "researcher"


@dataclass(frozen=True)
class DelegatedTask:
    """A focused task assigned to one specialized agent."""

    task_id: str
    prompt: str
    role: AgentRole = AgentRole.EXECUTOR
    context_state: ContextState | None = None


@dataclass(frozen=True)
class AgentResult:
    """Output and metrics from one delegated task."""

    task: DelegatedTask
    output: str
    metrics: AgentRunMetrics
    success: bool
    error: str | None = None


@dataclass(frozen=True)
class CoordinationResult:
    """Aggregated result from one or more delegated tasks."""

    results: list[AgentResult] = field(default_factory=list)

    @property
    def success(self) -> bool:
        """Return true when every delegated task completed successfully."""
        return bool(self.results) and all(result.success for result in self.results)

    @property
    def output(self) -> str:
        """Combine successful outputs in task order."""
        return "\n\n".join(result.output for result in self.results if result.output)
