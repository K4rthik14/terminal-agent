"""Unit tests for the lightweight evaluation harness."""

from context.metrics import AgentRunMetrics
from evaluation.harness import EvaluationHarness
from evaluation.models import EvaluationTask


class FakeAgent:
    def __init__(self, should_fail: bool = False) -> None:
        self.should_fail = should_fail
        self.last_run_metrics = AgentRunMetrics()

    def run(self, prompt: str) -> str:
        if self.should_fail:
            raise RuntimeError("task failed")
        self.last_run_metrics.record_tool("read_file")
        self.last_run_metrics.finish(True)
        return f"completed: {prompt}"


def test_harness_runs_tasks_and_collects_metrics() -> None:
    harness = EvaluationHarness(lambda: FakeAgent())
    report = harness.run(
        [
            EvaluationTask(name="readme", prompt="Read README.md"),
            EvaluationTask(name="status", prompt="Report status"),
        ]
    )

    assert report.total_count == 2
    assert report.success_count == 2
    assert report.results[0].metrics.tool_usage == {"read_file": 1}
    assert report.results[1].output == "completed: Report status"


def test_harness_records_task_failures_without_stopping() -> None:
    harness = EvaluationHarness(lambda: FakeAgent(should_fail=True))

    report = harness.run([EvaluationTask(name="broken", prompt="Fail")])

    assert report.total_count == 1
    assert report.success_count == 0
    assert report.results[0].error == "task failed"
    assert report.results[0].metrics.success is False
