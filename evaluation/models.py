"""Contracts for lightweight agent evaluation runs."""

from __future__ import annotations

from dataclasses import dataclass, field

from context.metrics import AgentRunMetrics


@dataclass(frozen=True)
class EvaluationTask:
    """One predefined prompt to execute."""

    name: str
    prompt: str


@dataclass(frozen=True)
class EvaluationResult:
    """Outcome and metrics for one evaluation task."""

    task: EvaluationTask
    output: str
    metrics: AgentRunMetrics
    error: str | None = None


@dataclass(frozen=True)
class EvaluationReport:
    """Collection of task results with a small aggregate summary."""

    results: list[EvaluationResult] = field(default_factory=list)

    @property
    def success_count(self) -> int:
        return sum(result.metrics.success for result in self.results)

    @property
    def total_count(self) -> int:
        return len(self.results)
