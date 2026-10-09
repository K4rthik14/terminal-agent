"""Paired, live-OpenRouter benchmark for trajectory-based recovery reflection.

Run with ``python -m evals.rlm_recovery_benchmark --allow-api-costs`` after
configuring an OpenRouter key. This runs the production OpenAI-compatible client
and Agent; it intentionally has no fake or scripted LLM fallback.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import shlex
import sys
import tempfile
import time
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from agent.agent import Agent
from cli.main import build_agent, build_llm, build_registry
from config.settings import Settings
from context.metrics import AgentRunMetrics
from llm.base import LLMClient
from utils.types import MessageList, StreamEvent
from verification.verifier import Verifier

TASKS_PATH = Path(__file__).with_name("rlm_recovery_tasks.json")


@dataclass(frozen=True)
class RecoveryTask:
    """A buggy starting workspace, coding prompt, and executable test contract."""

    id: str
    failure_type: str
    prompt: str
    files: dict[str, str]


class CountingLLM(LLMClient):
    """Count requests while delegating every response to the configured provider."""

    def __init__(self, client: LLMClient) -> None:
        self._client = client
        self.calls = 0

    def stream(
        self,
        messages: MessageList,
        tool_schemas: list[dict[str, Any]],
    ) -> Iterator[StreamEvent]:
        self.calls += 1
        yield from self._client.stream(messages, tool_schemas)


class QuietRenderer:
    """Provide the Agent renderer interface without interactive terminal output."""

    def thinking(self) -> None:
        pass

    def executing(self, tool_name: str, args: dict[str, Any]) -> float:
        return time.monotonic()

    def completed_tool(self, tool_name: str, success: bool, started_at: float) -> None:
        pass

    def completed(self) -> None:
        pass

    def info(self, message: str) -> None:
        pass


def load_tasks(path: Path = TASKS_PATH) -> list[RecoveryTask]:
    """Load the checked-in task fixtures in stable order."""
    raw_tasks = json.loads(path.read_text(encoding="utf-8"))
    return [
        RecoveryTask(
            id=str(item["id"]),
            failure_type=str(item["failure_type"]),
            prompt=str(item["prompt"]),
            files={str(name): str(content) for name, content in item["files"].items()},
        )
        for item in raw_tasks
    ]


def _verification_command() -> str:
    return f"{shlex.quote(sys.executable)} -B -m pytest -q -p no:cacheprovider test_solution.py"


def _write_fixture(task: RecoveryTask, root: Path) -> None:
    for relative_name, content in task.files.items():
        target = (root / relative_name).resolve()
        target.relative_to(root.resolve())
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")


def verify_initial_fixtures(tasks: list[RecoveryTask] | None = None) -> dict[str, bool]:
    """Confirm every fresh starter workspace fails its own test before an agent run."""
    fixture_tasks = tasks if tasks is not None else load_tasks()
    results: dict[str, bool] = {}
    for task in fixture_tasks:
        with tempfile.TemporaryDirectory(prefix=f"rlm-fixture-{task.id}-") as directory:
            workspace = Path(directory)
            _write_fixture(task, workspace)
            previous_cwd = Path.cwd()
            try:
                os.chdir(workspace)
                results[task.id] = not Verifier(timeout_seconds=30).verify_test(
                    _verification_command()
                ).passed
            finally:
                os.chdir(previous_cwd)
    return results


@contextlib.contextmanager
def _configured_environment(enabled: bool) -> Iterator[None]:
    values = {
        "AGENT_RLM_ENABLED": "true" if enabled else "false",
        "AGENT_VERIFICATION_COMMAND": _verification_command(),
        "AGENT_VERIFICATION_TIMEOUT_SECONDS": "30",
        "AGENT_APPROVAL_MODE": "never",
        "AGENT_MAX_ITERATIONS": "12",
        "AGENT_MAX_TOOL_CALLS": "60",
        "AGENT_MAX_EXECUTION_TIME_SECONDS": "240",
    }
    previous = {name: os.environ.get(name) for name in values}
    os.environ.update(values)
    try:
        yield
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def _assert_openrouter_configured(settings: Settings) -> None:
    if not settings.api_key:
        raise RuntimeError("No API key configured; set AGENT_API_KEY or OPENROUTER_API_KEY.")
    hostname = (urlparse(settings.base_url).hostname or "").lower()
    if hostname != "openrouter.ai" and not hostname.endswith(".openrouter.ai"):
        raise RuntimeError("The configured AGENT_BASE_URL is not an OpenRouter endpoint.")


def _new_agent(settings: Settings, llm: CountingLLM) -> Agent:
    def agent_factory() -> Agent:
        def sub_factory() -> Agent:
            return build_agent(settings, build_registry(settings, sub_factory), llm=llm)

        registry = build_registry(settings, sub_factory)
        return build_agent(settings, registry, renderer=QuietRenderer(), llm=llm)  # type: ignore[arg-type]

    return agent_factory()


def _run_task(task: RecoveryTask, enabled: bool) -> dict[str, Any]:
    with _configured_environment(enabled):
        settings = Settings()
        _assert_openrouter_configured(settings)
        with tempfile.TemporaryDirectory(prefix=f"rlm-live-{task.id}-") as directory:
            workspace = Path(directory)
            _write_fixture(task, workspace)
            previous_cwd = Path.cwd()
            try:
                os.chdir(workspace)
                llm = CountingLLM(build_llm(settings))
                agent = _new_agent(settings, llm)
                started = time.monotonic()
                with contextlib.redirect_stdout(io.StringIO()):
                    result = agent.run(task.prompt)
                elapsed = time.monotonic() - started
                metrics: AgentRunMetrics = result.metrics
                return {
                    "id": task.id,
                    "failure_type": task.failure_type,
                    "success": result.success and metrics.verification_passes > 0,
                    "recovered_after_failure": (
                        metrics.verification_failures > 0 and metrics.verification_passes > 0
                    ),
                    "repair_attempts": max(0, metrics.verification_attempts - 1),
                    "verification_attempts": metrics.verification_attempts,
                    "verification_failures": metrics.verification_failures,
                    "tool_calls": metrics.tool_calls,
                    "reflection_calls": metrics.rlm_reflections,
                    "reflection_failures": metrics.rlm_reflection_failures,
                    "llm_requests": llm.calls,
                    "execution_seconds": round(elapsed, 3),
                }
            finally:
                os.chdir(previous_cwd)


def _summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(results)
    recoveries = sum(1 for item in results if item["recovered_after_failure"])
    return {
        "tasks": total,
        "successes": sum(1 for item in results if item["success"]),
        "success_rate": sum(1 for item in results if item["success"]) / total if total else 0,
        "successful_recoveries": recoveries,
        "successful_recovery_rate": recoveries / total if total else 0,
        "verification_failures": sum(int(item["verification_failures"]) for item in results),
        "repair_attempts": sum(int(item["repair_attempts"]) for item in results),
        "tool_calls": sum(int(item["tool_calls"]) for item in results),
        "reflection_calls": sum(int(item["reflection_calls"]) for item in results),
        "reflection_failures": sum(int(item["reflection_failures"]) for item in results),
        "llm_requests": sum(int(item["llm_requests"]) for item in results),
        "mean_execution_seconds": round(
            sum(float(item["execution_seconds"]) for item in results) / total if total else 0,
            3,
        ),
        "provider_token_usage": None,
        "provider_token_usage_note": (
            "Not exposed by the current streaming client; no synthetic token estimate substituted."
        ),
    }


def _compare_modes(off: list[dict[str, Any]], on: list[dict[str, Any]]) -> dict[str, list[str]]:
    on_by_id = {str(item["id"]): item for item in on}
    categories: dict[str, list[str]] = {
        "helped": [],
        "no_outcome_change": [],
        "harmed": [],
    }
    for baseline in off:
        task_id = str(baseline["id"])
        baseline_passed = bool(baseline["success"])
        rlm_passed = bool(on_by_id[task_id]["success"])
        if rlm_passed and not baseline_passed:
            categories["helped"].append(task_id)
        elif baseline_passed and not rlm_passed:
            categories["harmed"].append(task_id)
        else:
            categories["no_outcome_change"].append(task_id)
    return categories


def run_benchmark(allow_api_costs: bool = False) -> dict[str, Any]:
    """Run paired live tasks; refuse provider calls unless the caller opts in."""
    if not allow_api_costs:
        raise RuntimeError(
            "This live benchmark can incur OpenRouter charges. Re-run with --allow-api-costs "
            "only if those requests are approved."
        )
    tasks = load_tasks()
    with _configured_environment(False):
        configured_settings = Settings()
        _assert_openrouter_configured(configured_settings)
        model = configured_settings.model
    initial = verify_initial_fixtures(tasks)
    failed_fixtures = [task_id for task_id, failed in initial.items() if not failed]
    if failed_fixtures:
        raise RuntimeError(f"Starter fixtures must fail before the agent runs: {failed_fixtures}")

    modes: dict[str, Any] = {}
    for enabled in (False, True):
        name = f"AGENT_RLM_ENABLED={'true' if enabled else 'false'}"
        results = [_run_task(task, enabled) for task in tasks]
        modes[name] = {"summary": _summarize(results), "results": results}
    return {
        "benchmark": "openrouter-trajectory-recovery-v1",
        "provider": "OpenRouter",
        "model": model,
        "task_ids": [task.id for task in tasks],
        "initial_fixtures_fail": initial,
        "outcome_comparison": _compare_modes(
            modes["AGENT_RLM_ENABLED=false"]["results"],
            modes["AGENT_RLM_ENABLED=true"]["results"],
        ),
        "modes": modes,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--allow-api-costs",
        action="store_true",
        help="Acknowledge that 24 task runs plus repair/reflection requests may incur charges.",
    )
    args = parser.parse_args(argv)
    try:
        print(json.dumps(run_benchmark(allow_api_costs=args.allow_api_costs), indent=2))
    except RuntimeError as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
