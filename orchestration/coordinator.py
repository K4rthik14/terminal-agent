"""Local multi-agent coordination layer."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Protocol

from agent.context import AgentContext
from context.metrics import AgentRunMetrics
from context.models import ContextState
from orchestration.models import (
    AgentResult,
    AgentRole,
    CoordinationResult,
    DelegatedTask,
)
from orchestration.router import RoleRouter


class RoleAgent(Protocol):
    """Minimal agent interface required by the coordinator."""

    last_run_metrics: AgentRunMetrics

    def run(self, prompt: str, context: AgentContext | None = None) -> str:
        """Run one focused task."""
        ...


AgentFactory = Callable[[AgentRole], RoleAgent]


class MultiAgentCoordinator:
    """Delegates isolated local tasks to specialized agent instances.

    Multi-agent behavior is opt-in. With ``enabled=False``, ``run`` executes a
    single executor task through the same agent interface as the current system.
    """

    def __init__(
        self,
        agent_factory: AgentFactory,
        enabled: bool = False,
        router: RoleRouter | None = None,
    ) -> None:
        self._agent_factory = agent_factory
        self._enabled = enabled
        self._router = router or RoleRouter()

    @property
    def enabled(self) -> bool:
        """Return whether role routing is enabled."""
        return self._enabled

    def run(self, prompt: str) -> CoordinationResult:
        """Route one prompt or pass it through as a single executor task."""
        task = (
            self._router.route(prompt)
            if self._enabled
            else DelegatedTask(task_id="task", prompt=prompt, role=AgentRole.EXECUTOR)
        )
        return self.run_tasks([task])

    def run_tasks(self, tasks: Iterable[DelegatedTask]) -> CoordinationResult:
        """Run delegated tasks sequentially with isolated contexts."""
        return CoordinationResult(results=[self._run_task(task) for task in tasks])

    def _run_task(self, task: DelegatedTask) -> AgentResult:
        agent = self._agent_factory(task.role)
        state = task.context_state or ContextState(goal=task.prompt)
        context = AgentContext(plan_mode=state.plan_mode)
        context.init_system_message()
        try:
            output = agent.run(task.prompt, context=context)
            metrics = agent.last_run_metrics
            return AgentResult(
                task=task,
                output=output,
                metrics=metrics,
                success=metrics.success,
            )
        except Exception as exc:
            metrics = getattr(agent, "last_run_metrics", AgentRunMetrics())
            metrics.finish(False)
            return AgentResult(
                task=task,
                output="",
                metrics=metrics,
                success=False,
                error=str(exc),
            )
