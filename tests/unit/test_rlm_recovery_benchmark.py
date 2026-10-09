"""No-network tests for the live OpenRouter recovery benchmark fixtures."""

from __future__ import annotations

import pytest

from config.settings import Settings
from evals.rlm_recovery_benchmark import (
    _configured_environment,
    load_tasks,
    run_benchmark,
    verify_initial_fixtures,
)


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


def test_benchmark_sets_and_restores_rlm_environment(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_RLM_ENABLED", "false")

    with _configured_environment(enabled=True):
        assert Settings().rlm_enabled is True

    assert Settings().rlm_enabled is False


def test_live_run_requires_explicit_cost_approval() -> None:
    with pytest.raises(RuntimeError, match="--allow-api-costs"):
        run_benchmark()
