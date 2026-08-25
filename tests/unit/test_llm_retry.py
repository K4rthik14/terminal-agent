"""Regression tests for bounded transient LLM retries."""

import time as time_module
from collections.abc import Iterable, Iterator
from types import SimpleNamespace
from typing import Any

import pytest

import agent.agent as agent_module
from agent.agent import Agent
from llm.openai_client import OpenAIClient
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


def make_agent(llm: Any, renderer: Any) -> Agent:
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


# --- Mid-stream transport failures -----------------------------------------
#
# The production failure: OpenAIClient.stream() only wrapped the request
# creation, so exceptions raised while *iterating* the response stream
# escaped as raw transport errors, bypassing the bounded retry path.

class FakeSDKStream:
    """Mimics an OpenAI SDK stream object: chunks arrive, then the transport dies."""

    def __init__(self, chunks: Iterable[SimpleNamespace], error: BaseException) -> None:
        self._chunks: Iterator[SimpleNamespace] = iter(chunks)
        self._error = error

    def __iter__(self) -> Any:
        return self

    def __next__(self) -> SimpleNamespace:
        try:
            return next(self._chunks)
        except StopIteration:
            raise self._error from None


def sdk_chunk(content: str = "", finish_reason: str | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                delta=SimpleNamespace(content=content or None, tool_calls=[]),
                finish_reason=finish_reason,
            )
        ]
    )


def make_client(monkeypatch: pytest.MonkeyPatch, sdk_stream: Any) -> OpenAIClient:
    client = OpenAIClient(api_key="test-key", model="test-model")
    monkeypatch.setattr(
        client._client.chat.completions, "create", lambda **kwargs: sdk_stream
    )
    return client


MIDSTREAM_SSL_FAILURE = (
    "ReadError: [SSL: RECORD_LAYER_FAILURE] record layer failure (_ssl.c:2711)"
)


def midstream_failure(error_text: str, partial: str = "partial") -> Iterator[StreamEvent]:
    """A stream() response that yields one token, then fails during iteration."""

    def generate() -> Iterator[StreamEvent]:
        yield StreamEvent(type="token", content=partial)
        raise LLMError(error_text)

    return generate()


def test_midstream_transport_failure_is_wrapped_as_transient_llm_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    failure = OSError(MIDSTREAM_SSL_FAILURE)
    client = make_client(monkeypatch, FakeSDKStream([sdk_chunk("partial ")], failure))

    with pytest.raises(LLMError) as excinfo:
        list(client.stream(messages=[], tool_schemas=[]))

    assert "RECORD_LAYER_FAILURE" in str(excinfo.value)
    # Transient classification is proven end-to-end by
    # test_openai_client_midstream_failure_recovers_through_agent_retry:
    # the agent retries only when the classifier accepts the message.


def test_openai_client_midstream_failure_recovers_through_agent_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(time_module, "sleep", lambda _: None)
    renderer = RecordingRenderer()
    client = OpenAIClient(api_key="test-key", model="test-model")
    attempts = iter([
        FakeSDKStream([sdk_chunk("partial ")], OSError(MIDSTREAM_SSL_FAILURE)),
        [sdk_chunk("recovered"), sdk_chunk(finish_reason="stop")],
    ])
    seen = 0

    def fake_create(**kwargs: Any) -> Any:
        nonlocal seen
        seen += 1
        return next(attempts)

    monkeypatch.setattr(client._client.chat.completions, "create", fake_create)
    agent = make_agent(client, renderer)

    assert agent.run("complete the task") == "recovered"
    assert seen == 2
    assert renderer.messages == ["Retrying LLM request (1/2)..."]


def test_midstream_transient_failure_is_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(time_module, "sleep", lambda _: None)
    renderer = RecordingRenderer()
    llm = SequenceLLM([
        midstream_failure(f"OpenAI API request failed: {MIDSTREAM_SSL_FAILURE}"),
        final("recovered"),
    ])
    agent = make_agent(llm, renderer)

    assert agent.run("complete the task") == "recovered"
    assert llm.calls == 2
    assert renderer.messages == ["Retrying LLM request (1/2)..."]


def test_partial_tokens_from_failed_attempt_do_not_leak_into_final_reply(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(time_module, "sleep", lambda _: None)
    renderer = RecordingRenderer()
    llm = SequenceLLM([
        midstream_failure(f"OpenAI API request failed: {MIDSTREAM_SSL_FAILURE}"),
        final("final answer"),
    ])
    agent = make_agent(llm, renderer)

    reply = agent.run("complete the task")

    assert reply == "final answer"
    assert agent.last_run_metrics.success is True


def test_midstream_retries_exhausted_return_clean_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(time_module, "sleep", lambda _: None)
    renderer = RecordingRenderer()
    error_text = f"OpenAI API request failed: {MIDSTREAM_SSL_FAILURE}"
    llm = SequenceLLM([
        midstream_failure(error_text),
        midstream_failure(error_text),
        midstream_failure(error_text),
    ])
    agent = make_agent(llm, renderer)

    reply = agent.run("complete the task")

    assert reply == f"Error: {error_text}"
    assert llm.calls == 3
    assert renderer.messages == [
        "Retrying LLM request (1/2)...",
        "Retrying LLM request (2/2)...",
    ]
    assert agent.last_run_metrics.success is False


def test_permanent_error_during_stream_is_not_retried(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(time_module, "sleep", lambda _: None)
    renderer = RecordingRenderer()
    llm = SequenceLLM([midstream_failure("OpenAI API request failed: 401 invalid api key")])
    agent = make_agent(llm, renderer)

    assert agent.run("complete the task") == "Error: OpenAI API request failed: 401 invalid api key"
    assert llm.calls == 1
    assert renderer.messages == []
