"""Regression tests for the structured AgentRunResult boundary (F1).

Covers: successful runs return a structured result; LLM failures are reported
structurally instead of as \"Error: ...\" output text; tool failures are contained
without crashing and a run that ends unsuccessfully is never reported as
success; SubAgentTool turns child failures into is_error ToolResults.
"""

import time as time_module
from types import SimpleNamespace
from typing import Any

from agent.agent import Agent
from agent.context import AgentContext
from context.metrics import AgentRunMetrics, AgentRunResult, AgentRunStatus
from tools.base import Tool
from tools.registry import ToolRegistry
from tools.sub_agent import SubAgentTool
from utils.errors import LLMError
from utils.types import StreamEvent, ToolResult

# --- Fakes -------------------------------------------------------------------


class QuietRenderer:
    def thinking(self) -> None:
        pass

    def info(self, message: str) -> None:
        pass

    def executing(self, name: str, args: dict) -> float:
        return 0.0

    def completed_tool(self, name: str, success: bool, started_at: float) -> None:
        pass

    def completed(self) -> None:
        pass


class SequenceLLM:
    """Consumes one scripted response per stream() call."""

    def __init__(self, responses: list[Any]) -> None:
        self.responses = iter(responses)
        self.calls = 0

    def stream(self, messages: Any, tool_schemas: Any) -> Any:
        self.calls += 1
        response = next(self.responses)
        if isinstance(response, Exception):
            raise response
        return iter(response)


def settings(**overrides: Any) -> Any:
    base: dict[str, Any] = {
        "plan_mode": False,
        "max_context_messages": 24,
        "approval_mode": "never",
        "max_iterations": 5,
        "max_tool_calls": 100,
        "max_execution_time_seconds": 0.0,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def make_agent(llm: Any, registry: ToolRegistry | None = None, **overrides: Any) -> Agent:
    return Agent(llm, registry or ToolRegistry(), settings(**overrides), renderer=QuietRenderer())


def final(text: str = "done") -> list[StreamEvent]:
    return [StreamEvent(type="token", content=text), StreamEvent(type="done", finish_reason="stop")]


def tool_call(name: str = "read_file", call_id: str = "c1", args: str = "{}") -> list[StreamEvent]:
    return [
        StreamEvent(
            type="tool_call_delta",
            tool_call_index=0,
            tool_call_id=call_id,
            tool_call_name=name,
            content=args,
        ),
        StreamEvent(type="done", finish_reason="tool_calls"),
    ]


def tool_result_contents(context: AgentContext) -> list[str]:
    return [str(m["content"]) for m in context.messages if m.get("role") == "tool"]


# --- Successful run -----------------------------------------------------------


def test_successful_run_returns_structured_success_result() -> None:
    agent = make_agent(SequenceLLM([final("all done")]))

    result = agent.run("complete the task")

    assert isinstance(result, AgentRunResult)
    assert result.success is True
    assert result.output == "all done"
    assert result.error is None
    assert result.status is AgentRunStatus.SUCCESS
    assert result.metrics.success is True
    assert agent.last_run_metrics.success is True


# --- LLM failure ---------------------------------------------------------------


def test_llm_failure_is_structured_not_successful_output(monkeypatch) -> None:
    monkeypatch.setattr(time_module, "sleep", lambda _: None)
    agent = make_agent(SequenceLLM([LLMError("401 invalid api key")]))

    result = agent.run("complete the task")

    assert result.success is False
    assert result.status is AgentRunStatus.LLM_ERROR
    assert "401 invalid api key" in (result.error or "")
    # The failure must not masquerade as agent output text.
    assert result.output == ""
    assert "Error:" not in result.output


# --- Tool / execution failure ---------------------------------------------------


class FailingTool(Tool):
    name = "read_file"
    description = "Always fails"
    parameters = {"type": "object", "properties": {}}  # noqa: RUF012
    is_read_only = True

    def run(self, args: dict) -> ToolResult:
        return ToolResult(tool_call_id="", content="boom: disk error", is_error=True)


def test_tool_failure_is_contained_and_run_that_ends_unsuccessfully_is_failure() -> None:
    llm = SequenceLLM([tool_call("read_file"), tool_call("read_file")])
    registry = ToolRegistry()
    registry.register(FailingTool())
    agent = make_agent(llm, registry, max_iterations=2)
    context = AgentContext()
    context.init_system_message()

    result = agent.run("fix the disk", context=context)

    # The tool error reached the model as a tool result instead of crashing.
    assert any("disk error" in content for content in tool_result_contents(context))
    # The run ended without completing, so it is a failure, never a success.
    assert result.success is False
    assert result.status is AgentRunStatus.BUDGET_EXCEEDED
    assert result.metrics.budget_exceeded is True
    assert result.metrics.tool_usage == {"read_file": 2}


class RaisingTool(Tool):
    name = "bash"
    description = "Raises every time"
    parameters = {"type": "object", "properties": {}}  # noqa: RUF012

    def run(self, args: dict) -> ToolResult:
        raise RuntimeError("command exploded")


def test_raising_tool_is_contained_and_agent_can_still_succeed() -> None:
    llm = SequenceLLM([tool_call("bash"), final("recovered")])
    registry = ToolRegistry()
    registry.register(RaisingTool())
    agent = make_agent(llm, registry)
    context = AgentContext()
    context.init_system_message()

    result = agent.run("run something", context=context)

    assert any("command exploded" in content for content in tool_result_contents(context))
    assert result.success is True
    assert result.output == "recovered"
    assert result.status is AgentRunStatus.SUCCESS


# --- Sub-agent failure -----------------------------------------------------------


class ScriptedChild:
    def __init__(self, result: AgentRunResult) -> None:
        self._result = result

    def run(self, prompt: str, context: Any = None) -> AgentRunResult:
        return self._result


def test_sub_agent_failure_becomes_tool_error() -> None:
    child = ScriptedChild(
        AgentRunResult(
            output="",
            success=False,
            error="LLM error: child provider down",
            metrics=AgentRunMetrics(),
            status=AgentRunStatus.LLM_ERROR,
        )
    )
    tool = SubAgentTool(lambda: child)

    result = tool.run({"description": "delegate", "prompt": "do it"})

    assert result.is_error is True
    assert "child provider down" in result.content


def test_sub_agent_success_is_a_normal_tool_result() -> None:
    child = ScriptedChild(
        AgentRunResult(
            output="child answer",
            success=True,
            error=None,
            metrics=AgentRunMetrics(),
            status=AgentRunStatus.SUCCESS,
        )
    )
    tool = SubAgentTool(lambda: child)

    result = tool.run({"description": "delegate", "prompt": "do it"})

    assert result.is_error is False
    assert result.content == "child answer"