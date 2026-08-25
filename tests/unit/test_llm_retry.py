"""Regression tests for bounded transient LLM retries."""

from types import SimpleNamespace

import agent.agent as agent_module
from agent.agent import Agent
from tools.registry import ToolRegistry
from utils.errors import LLMError
from utils.types import StreamEvent


class RecordingRenderer:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def thinking(self) -> None:
        pass

    def info(self, message: str) -> None:
        self.messages.append(message)

    def completed(self) -> None:
        pass


class SequenceLLM:
    def __init__(self, responses) -> None:
        self.responses = iter(responses)
        self.calls = 0

    def stream(self, messages, tool_schemas):
        self.calls += 1
        response = next(self.responses)
        if isinstance(response, Exception):
            raise response
        return iter(response)


def settings() -> SimpleNamespace:
    return SimpleNamespace(
        plan_mode=False,
        max_context_messages=24,
        approval_mode="never",
        max_iterations=5,
        max_tool_calls=100,
        max_execution_time_seconds=0.0,
    )


def final(text: str = "done") -> list[StreamEvent]:
    return [StreamEvent(type="token", content=text), StreamEvent(type="done", finish_reason="stop")]


def make_agent(llm, renderer):
    return Agent(llm, ToolRegistry(), settings(), renderer=renderer)


def test_transient_ssl_failure_retries_then_succeeds(monkeypatch) -> None:
    monkeypatch.setattr(agent_module.time, "sleep", lambda _: None)
    renderer = RecordingRenderer()
    llm = SequenceLLM([LLMError("SSL: RECORD_LAYER_FAILURE"), final("recovered")])

    agent = make_agent(llm, renderer)

    assert agent.run("complete the task") == "recovered"
    assert llm.calls == 2
    assert renderer.messages == ["Retrying LLM request (1/2)..."]


def test_exhausted_transient_retries_return_clean_error(monkeypatch) -> None:
    monkeypatch.setattr(agent_module.time, "sleep", lambda _: None)
    renderer = RecordingRenderer()
    failure = LLMError("connection reset by peer")
    llm = SequenceLLM([failure, failure, failure])

    agent = make_agent(llm, renderer)

    reply = agent.run("complete the task")

    assert reply == "Error: connection reset by peer"
    assert llm.calls == 3
    assert renderer.messages == [
        "Retrying LLM request (1/2)...",
        "Retrying LLM request (2/2)...",
    ]
    assert agent.last_run_metrics.success is False


def test_permanent_llm_error_is_not_retried(monkeypatch) -> None:
    monkeypatch.setattr(agent_module.time, "sleep", lambda _: None)
    renderer = RecordingRenderer()
    llm = SequenceLLM([LLMError("401 invalid api key")])

    agent = make_agent(llm, renderer)

    assert agent.run("complete the task") == "Error: 401 invalid api key"
    assert llm.calls == 1
    assert renderer.messages == []
