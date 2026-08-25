"""Delegation-path regression tests: SubAgentTool -> child Agent -> parent.

Covers the audited runtime contract: context isolation, shared safety rules,
child tool/LLM failure containment, result propagation, parent continuation,
plan-mode blocking, and a hard cap on delegation depth.
"""

import json
import time as time_module
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

import pytest

from agent.agent import Agent
from agent.context import AgentContext
from config.defaults import MAX_SUBAGENT_DEPTH
from tools import sub_agent as sub_agent_module
from tools.registry import ToolRegistry
from tools.sub_agent import SubAgentTool
from utils.errors import LLMError
from utils.types import StreamEvent

# --- Fakes -------------------------------------------------------------------


class RecordingRenderer:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def thinking(self) -> None:
        pass

    def info(self, message: str) -> None:
        self.messages.append(message)

    def executing(self, name: str, args: dict[str, Any]) -> float:
        return time_module.monotonic()

    def completed_tool(self, name: str, success: bool, started_at: float) -> None:
        pass

    def completed(self) -> None:
        pass


def settings(**overrides: Any) -> Any:
    base: dict[str, Any] = {
        "plan_mode": False,
        "max_context_messages": 24,
        "approval_mode": "never",
        "max_iterations": 10,
        "max_tool_calls": 100,
        "max_execution_time_seconds": 0.0,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


class ScriptedLLM:
    """Consumes one scripted response per stream() call across all holders."""

    def __init__(self, responses: list[Any]) -> None:
        self.responses = list(responses)
        self.calls = 0

    def stream(self, messages: Any, tool_schemas: Any) -> Any:
        self.calls += 1
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return iter(response)


def task_call(prompt: str, call_id: str = "t1") -> list[StreamEvent]:
    arguments = json.dumps({"description": "delegate", "prompt": prompt})
    return [
        StreamEvent(
            type="tool_call_delta",
            tool_call_id=call_id,
            tool_call_name="task",
            content=arguments,
        ),
        StreamEvent(type="done", finish_reason="tool_calls"),
    ]


def final(text: str) -> list[StreamEvent]:
    return [StreamEvent(type="token", content=text), StreamEvent(type="done", finish_reason="stop")]


def make_renderer() -> Any:
    return RecordingRenderer()


def make_agent(llm: Any, registry: ToolRegistry, **overrides: Any) -> Any:
    return Agent(llm, registry, settings(**overrides), renderer=make_renderer())


def make_agent_factory(llm: Any, created: list[Any]) -> Callable[[], Any]:
    """Build the same recursive factory shape cli/main.py uses."""

    def factory() -> Any:
        registry = ToolRegistry()
        registry.register(SubAgentTool(factory))
        agent = Agent(llm, registry, settings(), renderer=make_renderer())
        created.append(agent)
        return agent

    return factory


def tool_results(context: AgentContext) -> list[str]:
    return [str(m["content"]) for m in context.messages if m.get("role") == "tool"]


# --- Successful delegation ----------------------------------------------------


def test_child_result_is_returned_to_parent_and_parent_continues(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(time_module, "sleep", lambda _: None)
    parent_llm = ScriptedLLM([task_call("child job"), final("parent summary")])
    child_llm = ScriptedLLM([final("child report")])
    created: list[Any] = []
    factory = make_agent_factory(child_llm, created)

    registry = ToolRegistry()
    registry.register(SubAgentTool(factory))
    agent = make_agent(parent_llm, registry)
    context = AgentContext()
    context.init_system_message()

    reply = agent.run("use a sub-agent", context=context)

    assert reply == "parent summary"
    assert len(created) == 1
    # The child's final reply reached the parent conversation as a tool result.
    assert any("child report" in content for content in tool_results(context))


def test_child_receives_no_parent_context(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(time_module, "sleep", lambda _: None)

    captured: dict[str, Any] = {}

    class SpyChildAgent:
        last_run_metrics = SimpleNamespace(success=True)

        def run(self, prompt: str, context: Any = None) -> str:
            captured["prompt"] = prompt
            captured["context"] = context
            return "child done"

    registry = ToolRegistry()
    registry.register(SubAgentTool(lambda: SpyChildAgent()))
    llm = ScriptedLLM([task_call("isolated job"), final("ok")])
    agent = make_agent(llm, registry)
    parent_context = AgentContext()
    parent_context.init_system_message()
    parent_context.add_user_message("secret parent notes")

    agent.run("delegate", context=parent_context)

    assert captured["prompt"] == "isolated job"
    # The child is invoked without the parent's context object or history.
    assert captured["context"] is None


# --- Failure containment -------------------------------------------------------


def test_child_permanent_llm_failure_is_contained(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(time_module, "sleep", lambda _: None)
    parent_llm = ScriptedLLM([task_call("failing job"), final("reported failure")])
    failing_child = ScriptedLLM([LLMError("401 invalid api key")])
    created: list[Any] = []
    factory = make_agent_factory(failing_child, created)

    registry = ToolRegistry()
    registry.register(SubAgentTool(factory))
    agent = make_agent(parent_llm, registry)
    context = AgentContext()
    context.init_system_message()

    reply = agent.run("delegate", context=context)

    assert reply == "reported failure"
    assert any("401 invalid api key" in content for content in tool_results(context))


def test_malformed_arguments_return_clean_error_result() -> None:
    registry = ToolRegistry()
    tool = SubAgentTool(lambda: None)
    registry.register(tool)

    result = tool.run({})

    assert result.is_error is True
    assert result.content.startswith("Sub-agent error")


def test_child_exception_returns_error_result_to_parent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(time_module, "sleep", lambda _: None)

    def broken_factory() -> Any:
        raise RuntimeError("factory exploded")

    registry = ToolRegistry()
    registry.register(SubAgentTool(broken_factory))
    llm = ScriptedLLM([task_call("x"), final("survived")])
    agent = make_agent(llm, registry)
    context = AgentContext()
    context.init_system_message()

    reply = agent.run("delegate", context=context)

    assert reply == "survived"
    assert any("factory exploded" in content for content in tool_results(context))


# --- Safety rules ----------------------------------------------------------------


def test_plan_mode_blocks_delegation_at_the_parent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(time_module, "sleep", lambda _: None)
    llm = ScriptedLLM([task_call("should not run"), final("plan only")])
    created: list[Any] = []
    factory = make_agent_factory(ScriptedLLM([final("never")]), created)

    registry = ToolRegistry()
    registry.register(SubAgentTool(factory))
    agent = make_agent(llm, registry, plan_mode=True)
    context = AgentContext(plan_mode=True)
    context.init_system_message()

    reply = agent.run("try to delegate", context=context)

    assert reply == "plan only"
    assert created == []  # No child agent was ever constructed.
    assert any("Plan mode is on" in content for content in tool_results(context))


# --- Recursion bound --------------------------------------------------------------


def test_delegation_depth_is_capped(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(time_module, "sleep", lambda _: None)
    # Parent (depth 0) delegates to child (1), which delegates to grandchild (2),
    # whose own delegation attempt must be refused instead of recursing further.
    shared = ScriptedLLM([
        task_call("level-2"),   # parent -> child
        task_call("level-3"),   # child -> grandchild
        task_call("level-4"),   # grandchild -> MUST be refused by the depth guard
        final("leaf-done"),     # grandchild completes after the refusal
        final("mid-done"),      # child completes
        final("top-done"),      # parent completes
    ])
    created: list[Any] = []
    factory = make_agent_factory(shared, created)

    registry = ToolRegistry()
    registry.register(SubAgentTool(factory))
    agent = make_agent(shared, registry)
    created.append(agent)
    context = AgentContext()
    context.init_system_message()

    reply = agent.run("nested delegation", context=context)

    assert reply == "top-done"
    # Parent + exactly two nested levels: the fourth level was never spawned.
    assert len(created) == 3


def test_depth_guard_refuses_when_already_at_limit() -> None:
    token = sub_agent_module.SUBAGENT_DEPTH.set(MAX_SUBAGENT_DEPTH)
    try:
        tool = SubAgentTool(lambda: None)  # pragma: no cover - factory must not run
        result = tool.run({"description": "d", "prompt": "p"})
    finally:
        sub_agent_module.SUBAGENT_DEPTH.reset(token)

    assert result.is_error is True
    assert "depth" in result.content.lower()
