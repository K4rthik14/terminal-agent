"""No-network tests for the live OpenRouter recovery benchmark fixtures."""

from __future__ import annotations

from collections import Counter

import pytest

from config.settings import Settings
from evals.rlm_recovery_benchmark import (
    CountingTool,
    _configured_environment,
    _remove_generated_caches,
    _summarize,
    _workspace_integrity,
    _write_fixture,
    load_tasks,
    run_benchmark,
    verify_initial_fixtures,
)
from tools.file_write import WriteFileTool


def test_benchmark_has_twelve_distinct_coding_tasks() -> None:
    tasks = load_tasks()

    assert len(tasks) == 12
    assert len({task.id for task in tasks}) == 12
    assert len({task.failure_type for task in tasks}) >= 8
    assert all("solution.py" in task.files and "test_solution.py" in task.files for task in tasks)


def test_all_starter_workspaces_fail_their_verification() -> None:
    tasks = load_tasks()

    results = verify_initial_fixtures(tasks)

    assert set(results) == {task.id for task in tasks}
    assert all(results.values())


def test_counting_tool_delegates_and_counts_real_tool_invocations(tmp_path) -> None:
    counts: Counter[str] = Counter()
    write_file = CountingTool(WriteFileTool(), counts)

    result = write_file.run({"path": str(tmp_path / "output.txt"), "content": "ok\n"})

    assert result.is_error is False
    assert (tmp_path / "output.txt").read_text(encoding="utf-8") == "ok\n"
    assert counts == Counter({"write_file": 1})


def test_recovery_rate_uses_runs_that_actually_failed_first() -> None:
    results = [
        {
            "success": True,
            "recovered_after_failure": False,
            "verification_failures": 0,
            "verification_passes": 1,
            "verification_errors": 0,
            "fixture_integrity_passed": True,
            "repair_attempts": 0,
            "tool_calls": 1,
            "reflection_calls": 0,
            "reflection_failures": 0,
            "llm_requests": 2,
            "execution_seconds": 1.0,
        },
        {
            "success": True,
            "recovered_after_failure": True,
            "verification_failures": 1,
            "verification_passes": 1,
            "verification_errors": 0,
            "fixture_integrity_passed": True,
            "repair_attempts": 1,
            "tool_calls": 2,
            "reflection_calls": 1,
            "reflection_failures": 0,
            "llm_requests": 3,
            "execution_seconds": 2.0,
        },
        {
            "success": False,
            "recovered_after_failure": False,
            "verification_failures": 2,
            "verification_passes": 0,
            "verification_errors": 0,
            "fixture_integrity_passed": True,
            "repair_attempts": 1,
            "tool_calls": 2,
            "reflection_calls": 1,
            "reflection_failures": 0,
            "llm_requests": 4,
            "execution_seconds": 3.0,
        },
    ]

    summary = _summarize(results)

    assert summary["tasks_with_verification_failure"] == 2
    assert summary["successful_recoveries"] == 1
    assert summary["successful_recovery_rate"] == 0.5


def test_fixture_integrity_rejects_test_edits_and_extra_files(tmp_path) -> None:
    task = load_tasks()[0]
    protected_mtimes = _write_fixture(task, tmp_path)

    assert _workspace_integrity(task, tmp_path, protected_mtimes)

    (tmp_path / "test_solution.py").write_text("def test_changed(): pass\n", encoding="utf-8")
    assert not _workspace_integrity(task, tmp_path, protected_mtimes)

    (tmp_path / "test_solution.py").write_text(task.files["test_solution.py"], encoding="utf-8")
    (tmp_path / "extra.py").write_text("# unexpected\n", encoding="utf-8")
    assert not _workspace_integrity(task, tmp_path, protected_mtimes)


def test_generated_python_and_pytest_caches_are_removed(tmp_path) -> None:
    task = load_tasks()[0]
    protected_mtimes = _write_fixture(task, tmp_path)
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "__pycache__" / "solution.pyc").write_bytes(b"cache")
    (tmp_path / ".pytest_cache").mkdir()
    (tmp_path / ".pytest_cache" / "nodeids").write_text("[]", encoding="utf-8")

    _remove_generated_caches(tmp_path)

    assert _workspace_integrity(task, tmp_path, protected_mtimes)


def test_benchmark_sets_and_restores_rlm_environment(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_RLM_ENABLED", "false")

    with _configured_environment(enabled=True):
        assert Settings().rlm_enabled is True

    assert Settings().rlm_enabled is False


def test_live_run_requires_explicit_cost_approval() -> None:
    with pytest.raises(RuntimeError, match="--allow-api-costs"):
        run_benchmark()
