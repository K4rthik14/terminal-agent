"""Minimal evaluation runner around the existing Agent and Verifier.

Flow: task JSON -> runner -> existing Agent (isolated workspace) ->
judge / existing Verifier -> pass/fail -> metrics -> results JSON.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import tempfile
import time
from collections.abc import Callable
from pathlib import Path

from agent.agent import Agent
from cli.main import build_agent, build_registry
from config.settings import Settings
from context.metrics import AgentRunResult, AgentRunStatus

from evals import judge, metrics

AgentFactory = Callable[[], Agent]


def load_tasks(tasks_dir: str | Path) -> list[dict[str, object]]:
    """Load task JSON files from a directory, sorted by task id."""
    tasks: list[dict[str, object]] = []
    for path in sorted(Path(tasks_dir).glob("*.json")):
        with open(path, encoding="utf-8") as handle:
            tasks.append(json.load(handle))
    return tasks


def run_task(task: dict[str, object], agent_factory: AgentFactory) -> dict[str, object]:
    """Run one task in a fresh isolated temp workspace and return its record."""
    workspace = tempfile.mkdtemp(prefix="eval-workspace-")
    original_cwd = os.getcwd()
    try:
        os.chdir(workspace)
        started_at = time.monotonic()
        agent_error = None
        agent_result: AgentRunResult | None = None
        try:
            agent_result = agent_factory().run(str(task["prompt"]))
        except Exception as exc:  # keep the eval going even if the agent crashes
            agent_error = str(exc)
        passed, detail, failure_type = judge.check_result(str(task["verification_command"]))
        duration_seconds = round(time.monotonic() - started_at, 3)
        agent_success = agent_error is None and (agent_result is None or agent_result.success)
        if agent_error is not None:
            passed = False
            detail = agent_error
            failure_type = "llm_error"
        elif agent_result is not None and not agent_result.success:
            # Structured agent failure: never inferred from output text.
            passed = False
            detail = agent_result.error or agent_result.output or "agent execution failed"
            failure_type = {
                AgentRunStatus.LLM_ERROR: "llm_error",
                AgentRunStatus.BUDGET_EXCEEDED: "budget_exceeded",
            }.get(agent_result.status, "agent_failed")
        record: dict[str, object] = {
            "id": task["id"],
            "agent_success": agent_success,
            "passed": passed,
            "detail": detail,
            "duration_seconds": duration_seconds,
        }
        if agent_error is not None:
            record["agent_error"] = agent_error
        if not passed:
            record["failure_type"] = failure_type or "unknown_failure"
        return record
    finally:
        os.chdir(original_cwd)
        shutil.rmtree(workspace, ignore_errors=True)


def run_tasks(
    tasks: list[dict[str, object]],
    agent_factory: AgentFactory,
    results_dir: str | Path,
) -> dict[str, object]:
    """Run all tasks, persist a results JSON, and return the report."""
    results = [run_task(task, agent_factory) for task in tasks]
    report: dict[str, object] = {"results": results, "metrics": metrics.summarize(results)}
    results_dir = Path(results_dir)
    results_dir.mkdir(parents=True, exist_ok=True)
    (results_dir / "results.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def default_agent_factory(settings: Settings) -> AgentFactory:
    """Build agents exactly like the CLI composition root does."""

    def factory() -> Agent:
        def sub_factory() -> Agent:
            return build_agent(settings, build_registry(settings, sub_factory))

        return build_agent(settings, build_registry(settings, sub_factory))

    return factory


def resolve_settings(no_approval: bool = False) -> Settings:
    """Load evaluation settings and apply runner-only approval overrides."""
    settings = Settings()
    if no_approval:
        settings.approval_mode = "never"
    return settings


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: python -m evals.runner"""
    parser = argparse.ArgumentParser(
        prog="evals.runner",
        description="Run the minimal evaluation harness",
    )
    parser.add_argument("--tasks-dir", default=str(Path(__file__).parent / "tasks"))
    parser.add_argument("--results-dir", default=str(Path(__file__).parent / "results"))
    parser.add_argument(
        "--no-approval",
        action="store_true",
        help="Skip human approval for all evaluation tool calls",
    )
    args = parser.parse_args(argv)

    settings = resolve_settings(args.no_approval)
    if not settings.api_key:
        print("No API key found. Set AGENT_API_KEY or OPENROUTER_API_KEY.")
        return 1

    tasks = load_tasks(args.tasks_dir)
    if not tasks:
        print(f"No task JSON files found in {args.tasks_dir}")
        return 1

    report = run_tasks(tasks, default_agent_factory(settings), args.results_dir)
    print(json.dumps(report["metrics"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
