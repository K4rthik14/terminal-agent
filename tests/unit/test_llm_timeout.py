"""Regression tests for the configurable LLM request/streaming timeout."""

import time as time_module
from collections.abc import Iterable, Iterator
from types import SimpleNamespace
from typing import Any, ClassVar

import pytest
from pydantic import ValidationError

from agent.agent import Agent
from config.defaults import DEFAULT_LLM_TIMEOUT_SECONDS
from config.settings import Settings
from llm.openai_client import OpenAIClient
from tools.registry import ToolRegistry
from utils.errors import LLMError
from utils.types import StreamEvent

# --- Fakes (self-contained, matching repo test conventions) -----------------


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
    def __init__(self, responses: Any) -> None:
        self.responses = iter(responses)
        self.calls = 0

    def stream(self, messages: Any, tool_schemas: Any) -> Any:
        self.calls += 1
        response = next(self.responses)
        if isinstance(response, Exception):
            raise response
        return iter(response)


def settings() -> Any:
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


class SpySDKClient:
    """Records constructor kwargs and serves canned streams from create()."""

    instances: ClassVar[list["SpySDKClient"]] = []

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs
        self.create_calls = 0
        self.streams: Any = iter([])
        SpySDKClient.instances.append(self)

    @property
    def chat(self) -> Any:
        return SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs: Any) -> Any:
        self.create_calls += 1
        return next(self.streams)


@pytest.fixture
def spy_sdk(monkeypatch: pytest.MonkeyPatch) -> type[SpySDKClient]:
    SpySDKClient.instances = []
    monkeypatch.setattr("llm.openai_client.OpenAI", SpySDKClient)
    return SpySDKClient


# --- Timeout reaches the SDK client boundary --------------------------------


def test_default_timeout_is_forwarded_to_sdk(spy_sdk: type[SpySDKClient]) -> None:
    OpenAIClient(api_key="test-key", model="test-model")

    assert spy_sdk.instances[0].kwargs["timeout"] == DEFAULT_LLM_TIMEOUT_SECONDS


def test_explicit_timeout_is_forwarded_to_sdk(spy_sdk: type[SpySDKClient]) -> None:
    OpenAIClient(api_key="test-key", model="test-model", timeout=7.5)

    assert spy_sdk.instances[0].kwargs["timeout"] == 7.5


def test_none_timeout_preserves_provider_default(spy_sdk: type[SpySDKClient]) -> None:
    OpenAIClient(api_key="test-key", model="test-model", timeout=None)

    assert spy_sdk.instances[0].kwargs["timeout"] is None


# --- Settings plumbing -------------------------------------------------------


def make_settings(monkeypatch: pytest.MonkeyPatch, timeout: str | None = None) -> Settings:
    if timeout is None:
        monkeypatch.delenv("AGENT_LLM_TIMEOUT_SECONDS", raising=False)
    else:
        monkeypatch.setenv("AGENT_LLM_TIMEOUT_SECONDS", timeout)
    return Settings(_env_file=None)  # type: ignore[call-arg]  # pydantic-settings kwarg


def test_settings_timeout_defaults_to_safe_value(monkeypatch: pytest.MonkeyPatch) -> None:
    settings_obj = make_settings(monkeypatch)

    assert settings_obj.llm_timeout_seconds == DEFAULT_LLM_TIMEOUT_SECONDS


def test_settings_timeout_loads_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    settings_obj = make_settings(monkeypatch, timeout="30")

    assert settings_obj.llm_timeout_seconds == 30.0


def test_non_positive_timeout_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(ValidationError) as excinfo:
        make_settings(monkeypatch, timeout="-5")

    assert any("llm_timeout_seconds" in str(loc) for loc in excinfo.value.errors()[0]["loc"])


def test_build_llm_forwards_configured_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def spy_client(**kwargs: Any) -> Any:
        captured.update(kwargs)
        return SimpleNamespace(stream=lambda messages, tool_schemas: iter([]))

    monkeypatch.setattr("cli.main.OpenAIClient", spy_client)
    monkeypatch.setattr("cli.main.build_agent", lambda *a, **k: None)

    from cli.main import build_llm

    build_llm(make_settings(monkeypatch, timeout="45"))

    assert captured["timeout"] == 45.0


# --- Timeout errors enter the existing transient retry path ------------------


def test_timeout_error_is_transient_and_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(time_module, "sleep", lambda _: None)
    renderer = RecordingRenderer()
    llm = SequenceLLM([
        LLMError("OpenAI API request failed: Request timed out."),
        final("recovered"),
    ])
    agent = make_agent(llm, renderer)

    assert agent.run("complete the task").output == "recovered"
    assert llm.calls == 2
    assert renderer.messages == ["Retrying LLM request (1/2)..."]


def test_midstream_read_timeout_recovers_through_agent_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(time_module, "sleep", lambda _: None)
    renderer = RecordingRenderer()
    client = OpenAIClient(api_key="test-key", model="test-model")
    attempts = iter([
        FakeSDKStream([sdk_chunk("partial ")], OSError("The read operation timed out")),
        [sdk_chunk("recovered"), sdk_chunk(finish_reason="stop")],
    ])
    seen = 0

    def fake_create(**kwargs: Any) -> Any:
        nonlocal seen
        seen += 1
        return next(attempts)

    monkeypatch.setattr(client._client.chat.completions, "create", fake_create)
    agent = make_agent(client, renderer)

    assert agent.run("complete the task").output == "recovered"
    assert seen == 2
    assert renderer.messages == ["Retrying LLM request (1/2)..."]


def test_permanent_error_remains_non_retryable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(time_module, "sleep", lambda _: None)
    renderer = RecordingRenderer()
    llm = SequenceLLM([LLMError("OpenAI API request failed: Error code: 400 - invalid model")])
    agent = make_agent(llm, renderer)

    result = agent.run("complete the task")

    assert result.success is False
    assert result.error == "LLM error: OpenAI API request failed: Error code: 400 - invalid model"
    assert llm.calls == 1
    assert renderer.messages == []
