"""Aggregate pass/fail results into simple evaluation metrics."""

from __future__ import annotations


def summarize(results: list[dict[str, object]]) -> dict[str, float]:
    """Count pass/fail across task results and compute the success rate."""
    total = len(results)
    passed = sum(1 for result in results if result["passed"])
    failed = total - passed
    return {
        "total_tasks": total,
        "passed_tasks": passed,
        "failed_tasks": failed,
        "success_rate": (passed / total) if total else 0.0,
    }
