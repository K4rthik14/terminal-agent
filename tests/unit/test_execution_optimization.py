"""Unit tests for execution-loop safeguards."""

from context.loop import LoopDetector


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


def test_loop_detector_reset_starts_a_new_workflow() -> None:
    detector = LoopDetector(max_repeats=2)

    detector.observe("read_file", {"path": "README.md"})
    detector.reset()

    assert detector.observe("read_file", {"path": "README.md"}) is False
