"""Focused tests for the Agent execution budget."""

from types import SimpleNamespace


import agent.agent as agent_module
import context.metrics as metrics_module
from agent.agent import Agent
from tools.base import Tool
from tools.registry import ToolRegistry
from utils.types import StreamEvent, ToolResult


class FakeLLM:
    def __init__(self, responses: list[list[StreamEvent]]) -> None:
        self.responses = iter(responses)
        self.calls = 0

    def stream(self, messages, tool_schemas):
        self.calls += 1
        return iter(next(self.responses))


class RecordingTool(Tool):
    name = "read_file"
    description = "Record a read"
    parameters = {"type": "object", "properties": {}}  # noqa: RUF012
    is_read_only = True

    def __init__(self) -> None:
        self.calls = 0

    def run(self, args: dict) -> ToolResult:
        self.calls += 1
        return ToolResult(tool_call_id="", content="ok")


def settings(*, iterations: int = 5, tool_calls: int = 100, seconds: float = 0.0):
    return SimpleNamespace(
        plan_mode=False,
        max_context_messages=24,
        approval_mode="never",
        max_iterations=iterations,
        max_tool_calls=tool_calls,
        max_execution_time_seconds=seconds,
    )


def final(text: str = "done") -> list[StreamEvent]:
    return [StreamEvent(type="token", content=text), StreamEvent(type="done", finish_reason="stop")]


def tool_call() -> list[StreamEvent]:
    return [
        StreamEvent(
            type="tool_call_delta",
            tool_call_index=0,
            tool_call_id="call",
            tool_call_name="read_file",
            content="{}",
        ),
        StreamEvent(type="done", finish_reason="tool_calls"),
    ]


def make_agent(llm, registry, **kwargs):
    return Agent(llm, registry, settings(**kwargs))  # type: ignore[arg-type]


def test_iteration_limit_stops_without_another_llm_call() -> None:
    llm = FakeLLM([tool_call()])
    agent = make_agent(llm, ToolRegistry(), iterations=1)

    agent.run("keep working")

    assert llm.calls == 1
    assert agent.last_run_metrics.budget_exceeded is True
    assert agent.last_run_metrics.budget_exceeded_reason == "max_iterations"


def test_tool_call_limit_prevents_additional_tool_calls() -> None:
    tool = RecordingTool()
    registry = ToolRegistry()
    registry.register(tool)
    llm = FakeLLM([tool_call(), tool_call()])
    agent = make_agent(llm, registry, tool_calls=1)

    agent.run("read twice")

    assert tool.calls == 1
    assert llm.calls == 1
    assert agent.last_run_metrics.tool_calls == 1
    assert agent.last_run_metrics.budget_exceeded_reason == "max_tool_calls"


def test_execution_timeout_stops_before_llm_execution(monkeypatch) -> None:
    calls = 0

    def monotonic() -> float:
        nonlocal calls
        calls += 1
        return 0.0 if calls <= 2 else 1.0

    monkeypatch.setattr(agent_module.time, "monotonic", monotonic)
    monkeypatch.setattr(metrics_module.time, "monotonic", monotonic)
    llm = FakeLLM([final()])
    agent = make_agent(llm, ToolRegistry(), seconds=0.5)

    agent.run("time out")

    assert llm.calls == 1
    assert agent.last_run_metrics.budget_exceeded is True
    assert agent.last_run_metrics.budget_exceeded_reason == "max_execution_time"


def test_normal_execution_is_unchanged_when_budget_is_not_reached() -> None:
    llm = FakeLLM([final("complete")])
    agent = make_agent(llm, ToolRegistry())

    assert agent.run("finish").output == "complete"
    assert agent.last_run_metrics.success is True
    assert agent.last_run_metrics.budget_exceeded is False
