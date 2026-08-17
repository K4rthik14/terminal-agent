"""Focused tests for optional deterministic agent verification."""

from types import SimpleNamespace

from agent.agent import Agent

from tools.base import Tool
from tools.registry import ToolRegistry
from utils.types import StreamEvent, ToolResult


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


def tool_call_done(name: str, call_id: str, args: str, text: str = "") -> list[StreamEvent]:
    """Stream a single tool call: optional preamble text, the call, then done."""
    events = [StreamEvent(type="token", content=text)] if text else []
    events.append(
        StreamEvent(
            type="tool_call_delta",
            tool_call_index=0,
            tool_call_id=call_id,
            tool_call_name=name,
            content=args,
        )
    )
    events.append(StreamEvent(type="done", finish_reason="tool_calls"))
    return events


class RecordingTool(Tool):
    """Deterministic stand-in for a write tool that records its calls."""

    name = "write_file"
    description = "Write a file"
    parameters = {"type": "object", "properties": {"path": {"type": "string"}}}

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def run(self, args: dict) -> ToolResult:
        self.calls.append(args)
        return ToolResult(tool_call_id="", content=f"wrote {args.get('path')}")


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


def test_end_to_end_tool_execution_failure_repair_and_pass() -> None:
    """Full loop: tool call -> tool result -> candidate reply -> failed check -> repair -> pass."""
    tool = RecordingTool()
    registry = ToolRegistry()
    registry.register(tool)

    llm = FakeLLM(
        [
            tool_call_done("write_file", "call_1", '{"path": "test_x.py"}', text="Let me fix it."),
            done("candidate fix"),
            done("proper fix applied"),
        ]
    )
    verifier = FakeVerifier([result(False, error="1 failed"), result(True)])
    agent = Agent(llm, registry, settings(), verifier=verifier, verification_command="pytest -q")

    reply = agent.run("fix the failing test")

    assert reply == "proper fix applied"
    assert tool.calls == [{"path": "test_x.py"}]
    assert len(llm.requests) == 3

    # The executed tool result reached the model before the first check.
    second_messages = llm.requests[1][0]
    assert any(
        message.get("role") == "tool" and "wrote test_x.py" in str(message.get("content"))
        for message in second_messages
    )

    # The verification failure reached the model for the repair turn.
    third_messages = llm.requests[2][0]
    assert any("Verification failed" in str(message.get("content")) for message in third_messages)

    metrics = agent.last_run_metrics
    assert metrics.success is True
    assert metrics.verification_attempts == 2
    assert metrics.verification_failures == 1
    assert metrics.verification_passes == 1
    assert metrics.verification_errors == 1
    assert metrics.tool_usage == {"write_file": 1}


def test_no_verifier_preserves_immediate_completion() -> None:
    llm = FakeLLM([done()])
    agent = Agent(llm, ToolRegistry(), settings())

    assert agent.run("fix it") == "done"
    assert len(llm.requests) == 1
    assert agent.last_run_metrics.success is True
    assert agent.last_run_metrics.verification_attempts == 0


def test_whitespace_verification_command_is_disabled() -> None:
    llm = FakeLLM([done()])
    verifier = FakeVerifier([result(False, error="must not run")])
    agent = Agent(llm, ToolRegistry(), settings(), verifier=verifier, verification_command="   ")

    assert agent.run("fix it") == "done"
    assert verifier.commands == []
    assert agent.last_run_metrics.verification_attempts == 0


def test_failed_check_uses_output_detail_when_no_error_reaches_model() -> None:
    from verification.models import VerificationResult

    llm = FakeLLM([done("candidate"), done("repaired")])
    failed = VerificationResult(
        passed=False,
        check="test",
        command="pytest -q",
        output="tests failed badly",
    )
    verifier = FakeVerifier([failed, result(True)])
    agent = Agent(llm, ToolRegistry(), settings(), verifier=verifier, verification_command="pytest -q")

    assert agent.run("fix it") == "repaired"
    second_messages = llm.requests[1][0]
    assert any("tests failed badly" in str(message.get("content")) for message in second_messages)
    assert agent.last_run_metrics.verification_failures == 1
