"""Deterministic fault-injection benchmark for trajectory-based repair reflection.

Run with ``python -m evals.rlm_recovery_benchmark``. This uses a scripted LLM,
not a provider model: it measures the real Agent/verifier/reflection wiring and
illustrates controlled outcomes, not live-model quality.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agent.agent import Agent
from config.settings import Settings
from context.metrics import AgentRunMetrics
from rlm.reflection import RLMReflector
from tools.file_write import WriteFileTool
from tools.registry import ToolRegistry
from utils.types import StreamEvent
from verification.verifier import Verifier


@dataclass(frozen=True)
class RecoveryTask:
    id: str
    prompt: str
    tests: str
    initial_code: str
    baseline_repair: str
    reflection_repair: str
    reflection_strategy: str


TASKS = (
    RecoveryTask(
        id="strip-before-lowercase",
        prompt=(
            "Implement normalize_name(value) in solution.py: trim surrounding whitespace "
            "and lowercase the result."
        ),
        tests=(
            "from solution import normalize_name\n"
            "def test_trims_and_lowercases():\n"
            "    assert normalize_name('  Ada LOVELACE  ') == 'ada lovelace'\n"
        ),
        initial_code="def normalize_name(value):\n    return value.lower()\n",
        baseline_repair="def normalize_name(value):\n    return value.lower()\n",
        reflection_repair="def normalize_name(value):\n    return value.strip().lower()\n",
        reflection_strategy=(
            "Strip surrounding whitespace before lowercasing; the assertion includes padded input."
        ),
    ),
    RecoveryTask(
        id="even-negative-integers",
        prompt="Implement is_even(value) in solution.py for positive and negative integers.",
        tests=(
            "from solution import is_even\n"
            "def test_positive_and_negative_even_values():\n"
            "    assert is_even(4) is True\n"
            "    assert is_even(-3) is False\n"
        ),
        initial_code="def is_even(value):\n    return value % 2 == 1\n",
        baseline_repair="def is_even(value):\n    return value % 2 == 0\n",
        reflection_repair="def is_even(value):\n    return value % 2 == 0\n",
        reflection_strategy=(
            "Use remainder zero to identify even integers, including negative values."
        ),
    ),
    RecoveryTask(
        id="zero-divisor-contract",
        prompt=(
            "Implement safe_divide(a, b) in solution.py: return None when b is zero, "
            "otherwise return a / b."
        ),
        tests=(
            "from solution import safe_divide\n"
            "def test_division_contract():\n"
            "    assert safe_divide(8, 2) == 4\n"
            "    assert safe_divide(8, 0) is None\n"
        ),
        initial_code=(
            "def safe_divide(a, b):\n"
            "    if b == 0:\n"
            "        return 0\n"
            "    return a / b\n"
        ),
        baseline_repair=(
            "def safe_divide(a, b):\n"
            "    if b == 0:\n"
            "        return None\n"
            "    return a / b\n"
        ),
        reflection_repair=(
            "def safe_divide(a, b):\n"
            "    if b == 0:\n"
            "        return 0\n"
            "    return a / b\n"
        ),
        reflection_strategy="Keep a numeric fallback of 0 for division by zero.",
    ),
)


class QuietRenderer:
    """Suppress interactive rendering while leaving the Agent run path intact."""

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


def _text_events(text: str) -> list[StreamEvent]:
    return [StreamEvent(type="token", content=text), StreamEvent(type="done", finish_reason="stop")]


class ScenarioLLM:
    """Script a first attempt and a repair, using reflection only as a branch signal."""

    def __init__(self, task: RecoveryTask) -> None:
        self.task = task
        self.main_turn = 0
        self.llm_calls = 0
        self.reflection_calls = 0
        self.estimated_prompt_tokens = 0
        self.estimated_completion_tokens = 0

    def stream(self, messages: list[dict[str, Any]], tool_schemas: list[dict[str, Any]]):
        self.llm_calls += 1
        prompt_size = len(json.dumps(messages, ensure_ascii=False))
        self.estimated_prompt_tokens += (prompt_size + 3) // 4
        is_reflection = bool(
            messages
            and "Analyze the failed coding-agent attempt" in str(messages[0].get("content", ""))
        )
        if is_reflection:
            self.reflection_calls += 1
            response = json.dumps(
                {
                    "what_went_wrong": (
                        "The first implementation did not satisfy the failing assertion."
                    ),
                    "likely_root_cause": (
                        "The implementation overlooked the specific input contract."
                    ),
                    "next_strategy": self.task.reflection_strategy,
                }
            )
            self.estimated_completion_tokens += (len(response) + 3) // 4
            return iter(_text_events(response))

        if self.main_turn in (0, 2):
            repair = self.main_turn == 2
            code = (
                self.task.reflection_repair
                if repair and _reflection_is_in_context(messages)
                else self.task.baseline_repair
                if repair
                else self.task.initial_code
            )
            args = json.dumps({"path": "solution.py", "content": code})
            call_index = self.main_turn // 2
            events = [
                StreamEvent(
                    type="tool_call_delta",
                    tool_call_index=0,
                    tool_call_id=f"write-{call_index}",
                    tool_call_name="write_file",
                    content=args,
                ),
                StreamEvent(type="done", finish_reason="tool_calls"),
            ]
            self.estimated_completion_tokens += (len(args) + 3) // 4
        elif self.main_turn in (1, 3):
            response = "The requested implementation is in solution.py."
            events = _text_events(response)
            self.estimated_completion_tokens += (len(response) + 3) // 4
        else:
            raise RuntimeError(f"Unexpected scripted main-model turn {self.main_turn}")
        self.main_turn += 1
        return iter(events)


def _reflection_is_in_context(messages: list[dict[str, Any]]) -> bool:
    return any(
        "Reflection on the previous attempt:" in str(message.get("content", ""))
        for message in messages
    )


def _run_task(task: RecoveryTask, rlm_enabled: bool) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix=f"rlm-eval-{task.id}-") as workspace:
        root = Path(workspace)
        (root / "test_solution.py").write_text(task.tests, encoding="utf-8")
        previous_cwd = Path.cwd()
        os.chdir(root)
        try:
            llm = ScenarioLLM(task)
            os.environ["AGENT_RLM_ENABLED"] = "true" if rlm_enabled else "false"
            settings = Settings(
                approval_mode="never",
                max_iterations=4,
                max_context_messages=24,
                max_tool_calls=20,
                max_execution_time_seconds=30,
            )
            registry = ToolRegistry()
            registry.register(WriteFileTool())
            agent = Agent(
                llm=llm,
                registry=registry,
                settings=settings,
                renderer=QuietRenderer(),  # type: ignore[arg-type]
                verifier=Verifier(timeout_seconds=10),
                verification_command=(
                    f"rm -rf __pycache__ && {os.sys.executable} -m pytest -q test_solution.py"
                ),
                rlm_reflector=RLMReflector(llm) if settings.rlm_enabled else None,
            )
            started = time.monotonic()
            result = agent.run(task.prompt)
            wall_seconds = time.monotonic() - started
            run_metrics: AgentRunMetrics = result.metrics
            return {
                "id": task.id,
                "success": result.success and run_metrics.verification_passes > 0,
                "recovered_after_failure": (
                    run_metrics.verification_failures > 0 and run_metrics.verification_passes > 0
                ),
                "verification_attempts": run_metrics.verification_attempts,
                "verification_failures": run_metrics.verification_failures,
                "repair_attempts": max(0, run_metrics.verification_attempts - 1),
                "tool_calls": run_metrics.tool_calls,
                "execution_seconds": round(wall_seconds, 6),
                "reflection_calls": run_metrics.rlm_reflections,
                "reflection_failures": run_metrics.rlm_reflection_failures,
                "llm_calls_including_reflection": llm.llm_calls,
                "estimated_prompt_tokens": llm.estimated_prompt_tokens,
                "estimated_completion_tokens": llm.estimated_completion_tokens,
                "estimated_total_tokens": (
                    llm.estimated_prompt_tokens + llm.estimated_completion_tokens
                ),
            }
        finally:
            os.chdir(previous_cwd)


def _summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(results)
    sum_fields = (
        "verification_failures",
        "repair_attempts",
        "tool_calls",
        "reflection_calls",
        "reflection_failures",
        "llm_calls_including_reflection",
        "estimated_prompt_tokens",
        "estimated_completion_tokens",
        "estimated_total_tokens",
    )
    return {
        "tasks": total,
        "successes": sum(1 for item in results if item["success"]),
        "success_rate": sum(1 for item in results if item["success"]) / total if total else 0,
        "successful_recoveries": sum(1 for item in results if item["recovered_after_failure"]),
        **{field: sum(int(item[field]) for item in results) for field in sum_fields},
        "mean_execution_seconds": round(
            sum(float(item["execution_seconds"]) for item in results) / total if total else 0,
            6,
        ),
    }


def run_benchmark() -> dict[str, Any]:
    """Run identical tasks with the public RLM environment flag both off and on."""
    old_value = os.environ.get("AGENT_RLM_ENABLED")
    modes: dict[str, Any] = {}
    try:
        for enabled in (False, True):
            mode_name = f"AGENT_RLM_ENABLED={'true' if enabled else 'false'}"
            results = [_run_task(task, enabled) for task in TASKS]
            modes[mode_name] = {"summary": _summarize(results), "results": results}
    finally:
        if old_value is None:
            os.environ.pop("AGENT_RLM_ENABLED", None)
        else:
            os.environ["AGENT_RLM_ENABLED"] = old_value
    return {
        "benchmark": "trajectory-reflection-recovery-fault-injection-v1",
        "model": "deterministic scripted fake; no provider calls",
        "scope": (
            "Agent verification-and-repair loop with optional RLMReflector; "
            "excludes pre-execution brief"
        ),
        "token_accounting": (
            "approximate character/4 estimate from synthetic messages; "
            "not provider token usage"
        ),
        "tasks": [task.id for task in TASKS],
        "modes": modes,
    }


def main() -> int:
    report = run_benchmark()
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
