"""Focused tests for optional deterministic agent verification."""

from types import SimpleNamespace

from agent.agent import Agent

from tools.registry import ToolRegistry
from utils.types import StreamEvent


class FakeLLM:
    def __init__(self, responses: list[list[StreamEvent]]) -> None:
        self.responses = iter(responses)
        self.requests: list[tuple[list[dict], list[dict]]] = []

    def stream(self, messages, tool_schemas):
        self.requests.append((messages, tool_schemas))
        return iter(next(self.responses))


class FakeVerifier:
    def __init__(self, results) -> None:
        self.results = iter(results)
        self.commands: list[str] = []

    def verify_test(self, command: str):
        self.commands.append(command)
        return next(self.results)


def settings(max_iterations: int = 4):
    return SimpleNamespace(
        plan_mode=False,
        max_context_messages=24,
        approval_mode="never",
        max_iterations=max_iterations,
    )


def done(text: str = "done") -> list[StreamEvent]:
    return [StreamEvent(type="token", content=text), StreamEvent(type="done", finish_reason="stop")]


def result(passed: bool, *, error: str | None = None, timed_out: bool = False):
    from verification.models import VerificationResult

    return VerificationResult(
        passed=passed,
        check="test",
        command="pytest -q",
        error=error,
        timed_out=timed_out,
    )


def test_verification_passes_and_agent_completes() -> None:
    llm = FakeLLM([done()])
    verifier = FakeVerifier([result(True)])
    agent = Agent(llm, ToolRegistry(), settings(), verifier=verifier, verification_command="pytest -q")

    assert agent.run("fix it") == "done"
    assert len(llm.requests) == 1
    assert agent.last_run_metrics.verification_passes == 1


def test_verification_failure_is_added_to_context_and_retries() -> None:
    llm = FakeLLM([done("first"), done("second")])
    verifier = FakeVerifier([result(False, error="1 failed") , result(True)])
    agent = Agent(llm, ToolRegistry(), settings(), verifier=verifier, verification_command="pytest -q")

    assert agent.run("fix it") == "second"
    assert len(llm.requests) == 2
    assert any("Verification failed" in str(message.get("content")) for message in llm.requests[1][0])
    assert agent.last_run_metrics.verification_failures == 1


def test_verification_eventually_passes_after_repair() -> None:
    llm = FakeLLM([done("repair 1"), done("repair 2"), done("complete")])
    verifier = FakeVerifier([result(False, error="failure"), result(False, error="failure"), result(True)])
    agent = Agent(llm, ToolRegistry(), settings(), verifier=verifier, verification_command="pytest -q")

    assert agent.run("fix it") == "complete"
    assert agent.last_run_metrics.verification_attempts == 3


def test_verification_respects_iteration_limit() -> None:
    llm = FakeLLM([done("attempt 1"), done("attempt 2")])
    verifier = FakeVerifier([result(False, error="failure"), result(False, error="failure")])
    agent = Agent(llm, ToolRegistry(), settings(max_iterations=2), verifier=verifier, verification_command="pytest -q")

    assert agent.run("fix it") == "attempt 2"
    assert agent.last_run_metrics.success is False
    assert agent.last_run_metrics.verification_attempts == 2


def test_disabled_verification_preserves_immediate_completion() -> None:
    llm = FakeLLM([done()])
    verifier = FakeVerifier([result(False, error="must not run")])
    agent = Agent(llm, ToolRegistry(), settings(), verifier=verifier)

    assert agent.run("fix it") == "done"
    assert verifier.commands == []
    assert agent.last_run_metrics.verification_attempts == 0


def test_verification_timeout_is_safe_and_repairable() -> None:
    llm = FakeLLM([done("retry"), done("complete")])
    verifier = FakeVerifier([result(False, error="timed out", timed_out=True), result(True)])
    agent = Agent(llm, ToolRegistry(), settings(), verifier=verifier, verification_command="pytest -q")

    assert agent.run("fix it") == "complete"
    assert agent.last_run_metrics.verification_errors == 1
