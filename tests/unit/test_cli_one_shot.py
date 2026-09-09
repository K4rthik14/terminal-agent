"""One-shot CLI exit-status tests for the AgentRunResult boundary (F1).

Covers: a successful one-shot run exits 0; a failed run exits non-zero and
still surfaces a human-readable failure reason.
"""

import sys
from types import SimpleNamespace

import pytest

import cli.main as cli_main
from context.metrics import AgentRunMetrics, AgentRunResult, AgentRunStatus


class StubAgent:
    def __init__(self, result: AgentRunResult) -> None:
        self._result = result

    def run(self, prompt: str, context=None, rlm_result=None) -> AgentRunResult:
        return self._result


def make_settings() -> SimpleNamespace:
    return SimpleNamespace(
        model="test-model",
        api_key="test-key",
        base_url=None,
        max_tokens=1000,
        llm_timeout_seconds=30.0,
        firecrawl_api_key="",
        max_web_content_length=10000,
        plan_mode=False,
        approval_mode="never",
        max_context_messages=24,
        rlm_enabled=False,
        verification_command="",
        verification_timeout_seconds=30.0,
        log_level="info",
    )


def run_one_shot(
    monkeypatch: pytest.MonkeyPatch,
    result: AgentRunResult,
    *extra_args: str,
) -> int:
    """Run cli.main.main() in one-shot mode and return its exit code."""
    monkeypatch.setattr(sys, "argv", ["reflex", "--prompt", "hello", *extra_args])
    monkeypatch.setattr(cli_main, "resolve_settings", lambda args: make_settings())
    monkeypatch.setattr(cli_main, "build_llm", lambda settings: None)
    monkeypatch.setattr(cli_main, "build_agent", lambda *a, **k: StubAgent(result))
    try:
        cli_main.main()
        return 0
    except SystemExit as exc:
        return exc.code


def test_one_shot_agent_success_exits_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    result = AgentRunResult(
        output="done",
        success=True,
        error=None,
        metrics=AgentRunMetrics(),
        status=AgentRunStatus.SUCCESS,
    )

    assert run_one_shot(monkeypatch, result) == 0


def test_one_shot_llm_failure_exits_nonzero(monkeypatch: pytest.MonkeyPatch) -> None:
    result = AgentRunResult(
        output="",
        success=False,
        error="LLM error: 401 invalid api key",
        metrics=AgentRunMetrics(),
        status=AgentRunStatus.LLM_ERROR,
    )

    assert run_one_shot(monkeypatch, result) != 0


def test_one_shot_budget_failure_exits_nonzero_and_renders_reason(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    result = AgentRunResult(
        output="partial work",
        success=False,
        error="Execution budget exceeded: max_iterations",
        metrics=AgentRunMetrics(),
        status=AgentRunStatus.BUDGET_EXCEEDED,
    )

    code = run_one_shot(monkeypatch, result)

    assert code != 0
    assert "max_iterations" in capsys.readouterr().out