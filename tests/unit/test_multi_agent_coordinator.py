"""Unit tests for local multi-agent coordination."""

from context.metrics import AgentRunMetrics
from orchestration.coordinator import MultiAgentCoordinator
from orchestration.models import AgentRole, DelegatedTask


class FakeAgent:
    def __init__(self, role: AgentRole) -> None:
        self.role = role
        self.last_run_metrics = AgentRunMetrics()
        # Hold the context objects themselves: comparing id() of garbage-collected
        # contexts is unreliable because CPython may recycle addresses.
        self.contexts: list[object] = []

    def run(self, prompt: str, context=None) -> str:
        self.contexts.append(context)
        self.last_run_metrics.finish(True)
        return f"{self.role.value}: {prompt}"


def test_coordinator_is_disabled_by_default() -> None:
    roles: list[AgentRole] = []

    def factory(role: AgentRole) -> FakeAgent:
        roles.append(role)
        return FakeAgent(role)

    result = MultiAgentCoordinator(factory).run("Create a file")

    assert result.success is True
    assert result.output == "executor: Create a file"
    assert roles == [AgentRole.EXECUTOR]


def test_enabled_coordinator_routes_to_specialized_role() -> None:
    roles: list[AgentRole] = []

    def factory(role: AgentRole) -> FakeAgent:
        roles.append(role)
        return FakeAgent(role)

    result = MultiAgentCoordinator(factory, enabled=True).run("Review the implementation")

    assert result.success is True
    assert roles == [AgentRole.REVIEWER]
    assert result.results[0].task.role == AgentRole.REVIEWER


def test_coordinator_isolates_context_per_task_and_aggregates_results() -> None:
    agents: list[FakeAgent] = []

    def factory(role: AgentRole) -> FakeAgent:
        agent = FakeAgent(role)
        agents.append(agent)
        return agent

    tasks = [
        DelegatedTask(task_id="one", prompt="Plan the change", role=AgentRole.PLANNER),
        DelegatedTask(task_id="two", prompt="Run the tests", role=AgentRole.EXECUTOR),
    ]
    result = MultiAgentCoordinator(factory, enabled=True).run_tasks(tasks)

    assert result.success is True
    assert len(result.results) == 2
    assert len(agents) == 2
    assert agents[0].contexts[0] is not agents[1].contexts[0]
    assert "planner: Plan the change" in result.output
    assert "executor: Run the tests" in result.output


def test_coordinator_records_task_failure() -> None:
    class FailingAgent(FakeAgent):
        def run(self, prompt: str, context=None) -> str:
            raise RuntimeError("agent failed")

    result = MultiAgentCoordinator(lambda role: FailingAgent(role), enabled=True).run("Research docs")

    assert result.success is False
    assert result.results[0].error == "agent failed"
    assert result.results[0].metrics.success is False
