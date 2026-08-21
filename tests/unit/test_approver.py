"""Tests for the human approval gate.

Covers the approval policy matrix, prompt answer parsing (including invalid
input), safe-default denial, and summary rendering without value leakage.
"""

import pytest

from agent.approver import Approver
from utils.types import ApprovalDecision, ApprovalMode, ToolCall


def _call(name: str = "bash", arguments: str = "{}") -> ToolCall:
    return ToolCall(id="t1", name=name, arguments=arguments)


def _approve_with(monkeypatch, answers: list[str]) -> ApprovalDecision:
    inputs = iter(answers)
    monkeypatch.setattr("builtins.input", lambda *_: next(inputs))
    return Approver(ApprovalMode.AUTO).request(_call(), {"command": "ls"})


def test_policy_auto_requires_approval_for_write_tools() -> None:
    assert Approver(ApprovalMode.AUTO).requires_approval(False) is True
    assert Approver(ApprovalMode.AUTO).requires_approval(True) is False


def test_policy_always_and_never() -> None:
    assert Approver(ApprovalMode.ALWAYS).requires_approval(True) is True
    assert Approver(ApprovalMode.ALWAYS).requires_approval(False) is True
    assert Approver(ApprovalMode.NEVER).requires_approval(False) is False
    assert Approver(ApprovalMode.NEVER).requires_approval(True) is False


@pytest.mark.parametrize("answer", ["y", "Y", "yes", "YES"])
def test_affirmative_answers_approve(monkeypatch, answer: str) -> None:
    assert _approve_with(monkeypatch, [answer]) == ApprovalDecision.APPROVED


@pytest.mark.parametrize("answer", ["n", "N", "no", ""])
def test_negative_or_empty_answers_deny(monkeypatch, answer: str) -> None:
    assert _approve_with(monkeypatch, [answer]) == ApprovalDecision.REJECTED


def test_invalid_input_reprompts_then_denies(monkeypatch) -> None:
    assert _approve_with(monkeypatch, ["maybe", "approve it", "n"]) == (
        ApprovalDecision.REJECTED
    )


def test_invalid_input_reprompt_then_approve(monkeypatch) -> None:
    assert _approve_with(monkeypatch, ["ok", "y"]) == ApprovalDecision.APPROVED


def test_eof_denies(monkeypatch) -> None:
    def _raise(*_):
        raise EOFError

    monkeypatch.setattr("builtins.input", _raise)
    assert Approver(ApprovalMode.AUTO).request(_call(), {}) == ApprovalDecision.REJECTED


def test_keyboard_interrupt_denies(monkeypatch) -> None:
    def _raise(*_):
        raise KeyboardInterrupt

    monkeypatch.setattr("builtins.input", _raise)
    assert Approver(ApprovalMode.AUTO).request(_call(), {}) == ApprovalDecision.REJECTED


def test_sequential_requests_decide_independently(monkeypatch) -> None:
    inputs = iter(["y", "n"])
    monkeypatch.setattr("builtins.input", lambda *_: next(inputs))
    approver = Approver(ApprovalMode.ALWAYS)
    first = approver.request(_call(), {"command": "mkdir x"})
    second = approver.request(_call(), {"command": "rm x"})
    assert (first, second) == (ApprovalDecision.APPROVED, ApprovalDecision.REJECTED)


def test_summary_truncates_long_commands() -> None:
    long_command = "echo " + "x" * 200
    summary = Approver._summary("bash", {"command": long_command})
    assert len(summary) <= 100
    assert summary.endswith("...")


def test_prompt_shows_action_details(monkeypatch) -> None:
    prompts: list[str] = []
    inputs = iter(["y"])

    def _fake_input(prompt: str = "") -> str:
        prompts.append(prompt)
        return next(inputs)

    monkeypatch.setattr("builtins.input", _fake_input)
    decision = Approver(ApprovalMode.AUTO).request(
        _call(name="write_file"), {"path": "/tmp/example.txt"}
    )
    assert decision == ApprovalDecision.APPROVED
    rendered = "\n".join(prompts)
    assert "write_file" in rendered
    assert "example.txt" in rendered
    assert "[y/N]" in rendered
