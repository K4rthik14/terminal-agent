"""Lightweight sequential evaluation harness."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Protocol

from context.metrics import AgentRunMetrics
from evaluation.models import EvaluationReport, EvaluationResult, EvaluationTask


class AgentRunner(Protocol):
    """Minimal interface required by the evaluation harness."""

    last_run_metrics: AgentRunMetrics

    def run(self, prompt: str) -> str:
        """Execute one prompt and return the final response."""
        ...


AgentFactory = Callable[[], AgentRunner]


class EvaluationHarness:
    """Executes predefined tasks sequentially with isolated agent runs."""

    def __init__(self, agent_factory: AgentFactory | AgentRunner) -> None:
        self._agent_factory = (
            agent_factory if callable(agent_factory) else lambda: agent_factory
        )

    def run(self, tasks: Iterable[EvaluationTask]) -> EvaluationReport:
        """Run all tasks and return their outputs and execution metrics."""
        results = [self.run_task(task) for task in tasks]
        return EvaluationReport(results=results)

    def run_task(self, task: EvaluationTask) -> EvaluationResult:
        """Run one task without stopping the harness on task failure."""
        agent = self._agent_factory()
        try:
            output = agent.run(task.prompt)
            return EvaluationResult(task=task, output=output, metrics=agent.last_run_metrics)
        except Exception as exc:
            metrics = getattr(agent, "last_run_metrics", AgentRunMetrics())
            metrics.finish(False)
            return EvaluationResult(
                task=task,
                output="",
                metrics=metrics,
                error=str(exc),
            )
