"""Unit tests for execution-loop safeguards."""

from context.loop import LoopDetector
from context.metrics import AgentRunMetrics
from context.models import ContextState
from context.scheduler import ToolScheduler
from tools.bash import BashTool
from tools.file_read import ReadFileTool
from tools.file_write import WriteFileTool


def test_run_metrics_records_execution_data() -> None:
    metrics = AgentRunMetrics()

    metrics.record_tool("read_file")
    metrics.record_tool("read_file")
    metrics.record_context(2, 100, 1)
    metrics.finish(True)

    assert metrics.success is True
    assert metrics.execution_time >= 0
    assert metrics.tool_usage == {"read_file": 2}
    assert metrics.context_message_counts == [2]


def test_loop_detector_blocks_repeated_identical_calls() -> None:
    detector = LoopDetector(max_repeats=2)

    assert detector.observe("read_file", {"path": "README.md"}) is False
    assert detector.observe("read_file", {"path": "README.md"}) is True


def test_loop_detector_canonicalizes_argument_order() -> None:
    detector = LoopDetector(max_repeats=2)

    detector.observe("bash", {"command": "pwd", "timeout": 30})
    assert detector.observe("bash", {"timeout": 30, "command": "pwd"}) is True


def test_loop_detector_allows_valid_different_steps() -> None:
    detector = LoopDetector(max_repeats=2)

    assert detector.observe("read_file", {"path": "main.py"}) is False
    assert detector.observe("edit_file", {"path": "main.py"}) is False
    assert detector.observe("bash", {"command": "pytest"}) is False


def test_loop_detector_allows_reread_after_another_tool() -> None:
    detector = LoopDetector(max_repeats=2)

    detector.observe("read_file", {"path": "main.py"})
    detector.observe("edit_file", {"path": "main.py"})

    assert detector.observe("read_file", {"path": "main.py"}) is False


def test_loop_detector_reset_starts_a_new_workflow() -> None:
    detector = LoopDetector(max_repeats=2)

    detector.observe("read_file", {"path": "README.md"})
    detector.reset()

    assert detector.observe("read_file", {"path": "README.md"}) is False


def test_tool_scheduler_exposes_relevant_tools_only() -> None:
    state = ContextState(goal="Read README.md")
    tools = [ReadFileTool(), WriteFileTool(), BashTool()]

    scheduled = ToolScheduler().schedule(state, tools)

    assert [tool.name for tool in scheduled] == ["read_file"]


def test_tool_scheduler_preserves_available_tools_for_unknown_tasks() -> None:
    state = ContextState(goal="Do something unusual")
    tools = [ReadFileTool(), WriteFileTool(), BashTool()]

    scheduled = ToolScheduler().schedule(state, tools)

    assert [tool.name for tool in scheduled] == ["read_file", "write_file", "bash"]
