"""Focused tests for the minimal evaluation harness (evals/)."""

from __future__ import annotations

import json
import os
from pathlib import Path

from evals import judge, metrics, runner

EVALS_TASKS_DIR = Path(__file__).parents[2] / "evals" / "tasks"


class FakeAgent:
    """Writes the given files relative to the current working directory."""

    def __init__(self, files: dict[str, str]) -> None:
        self.files = files
        self.prompts: list[str] = []

    def run(self, prompt: str, context=None) -> str:
        self.prompts.append(prompt)
        for name, content in self.files.items():
            path = Path(name)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        return "done"


class SolvingAgent:
    """Solves all three built-in tasks by inspecting the prompt."""

    def run(self, prompt: str, context=None) -> str:
        if "hello.txt" in prompt:
            Path("hello.txt").write_text("hello\n", encoding="utf-8")
        elif "src" in prompt:
            Path("src").mkdir(exist_ok=True)
            (Path("src") / "README.md").write_text("# my-project\n", encoding="utf-8")
        elif "run.sh" in prompt:
            Path("run.sh").write_text("#!/bin/sh\necho done\n", encoding="utf-8")
        return "done"


def passing_agent_factory():
    return lambda: FakeAgent({"hello.txt": "hello\n"})


def failing_agent_factory():
    return lambda: FakeAgent({})


def solving_agent_factory():
    return lambda: SolvingAgent()


# --- judge ---


def test_judge_passes_when_command_succeeds(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "hello.txt").write_text("hello\n", encoding="utf-8")

    passed, detail = judge.check("grep -qx hello hello.txt")

    assert passed is True
    assert detail == ""


def test_judge_fails_when_command_fails(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    passed, detail = judge.check("grep -qx hello hello.txt")

    assert passed is False
    assert detail  # e.g. "Command exited with code 1."


# --- metrics ---


def test_metrics_summarize_counts_and_success_rate() -> None:
    results = [
        {"id": "a", "passed": True},
        {"id": "b", "passed": False},
        {"id": "c", "passed": True},
    ]

    assert metrics.summarize(results) == {
        "total_tasks": 3,
        "passed_tasks": 2,
        "failed_tasks": 1,
        "success_rate": 2 / 3,
    }


def test_metrics_summarize_empty_has_zero_rate() -> None:
    assert metrics.summarize([]) == {
        "total_tasks": 0,
        "passed_tasks": 0,
        "failed_tasks": 0,
        "success_rate": 0.0,
    }


# --- runner ---


def test_run_task_passes_in_isolated_workspace_and_restores_cwd(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    task = {"id": "t1", "prompt": "make hello.txt", "verification_command": "grep -qx hello hello.txt"}

    result = runner.run_task(task, passing_agent_factory())

    assert result["id"] == "t1"
    assert result["passed"] is True
    assert result["detail"] == ""
    assert result["duration_seconds"] >= 0
    assert os.getcwd() == str(tmp_path)


def test_run_task_fails_when_verification_fails() -> None:
    task = {"id": "t1", "prompt": "make hello.txt", "verification_command": "grep -qx hello hello.txt"}

    result = runner.run_task(task, failing_agent_factory())

    assert result["passed"] is False
    assert result["detail"]
    assert result["failure_type"] == "verification_failed"
    assert result["duration_seconds"] >= 0


def test_run_task_records_agent_error() -> None:
    task = {"id": "t1", "prompt": "make hello.txt", "verification_command": "grep -qx hello hello.txt"}

    class BrokenAgent:
        def run(self, prompt: str, context=None) -> str:
            raise RuntimeError("boom")

    result = runner.run_task(task, lambda: BrokenAgent())

    assert result["passed"] is False
    assert result["agent_error"] == "boom"
    assert result["failure_type"] == "llm_error"
    assert result["duration_seconds"] >= 0


def test_run_tasks_writes_results_json_and_metrics(tmp_path) -> None:
    tasks = [
        {"id": "pass", "prompt": "p1", "verification_command": "grep -qx hello hello.txt"},
        {"id": "fail", "prompt": "p2", "verification_command": "grep -qx hello hello.txt"},
    ]
    calls = {"n": 0}

    def alternating_factory():
        def factory():
            calls["n"] += 1
            return FakeAgent({"hello.txt": "hello\n"}) if calls["n"] == 1 else FakeAgent({})

        return factory

    results_dir = tmp_path / "results"
    report = runner.run_tasks(tasks, alternating_factory(), results_dir)

    assert report["metrics"] == {
        "total_tasks": 2,
        "passed_tasks": 1,
        "failed_tasks": 1,
        "success_rate": 0.5,
    }
    stored = json.loads((results_dir / "results.json").read_text(encoding="utf-8"))
    assert stored == report


def test_load_tasks_returns_minimal_task_fields() -> None:
    tasks = runner.load_tasks(EVALS_TASKS_DIR)

    assert [task["id"] for task in tasks] == [f"task-{index:03d}" for index in range(1, 16)]
    for task in tasks:
        assert set(task) == {"id", "prompt", "verification_command"}


def test_builtin_tasks_pass_with_solving_agent(tmp_path) -> None:
    tasks = runner.load_tasks(EVALS_TASKS_DIR)

    report = runner.run_tasks(tasks, solving_agent_factory(), tmp_path / "results")

    assert report["metrics"]["total_tasks"] == 15
    assert report["metrics"]["passed_tasks"] == 1
    assert report["metrics"]["failed_tasks"] == 14
    assert report["metrics"]["success_rate"] == 1 / 15
