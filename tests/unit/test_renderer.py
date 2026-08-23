"""Tests for the terminal renderer presentation layer.

Verifies the visual contract: compact one-line tool activity, honest
success/failure markers, and graceful handling of long paths and commands.
"""

from cli.renderer import Renderer, _ellipsize, _shorten_path


def test_executing_renders_single_compact_line(capsys) -> None:
    renderer = Renderer()
    started = renderer.executing("bash", {"command": "rm -rf build/"})
    out = capsys.readouterr().out
    assert isinstance(started, float)
    assert out.count("\n") == 1  # exactly one line, no multi-line cards
    assert "Run command" in out
    assert "rm -rf build/" in out


def test_completed_tool_success_and_failure_markers(capsys) -> None:
    renderer = Renderer()
    renderer.completed_tool("bash", True, 0.0)
    success_out = capsys.readouterr().out
    assert "✓" in success_out
    assert "failed" not in success_out

    renderer.completed_tool("bash", False, 0.0)
    failure_out = capsys.readouterr().out
    assert "✗" in failure_out
    assert "failed" in failure_out


def test_error_prefix_rendered(capsys) -> None:
    Renderer().error("something went wrong")
    out = capsys.readouterr().out
    assert "✗ Error:" in out
    assert "something went wrong" in out


def test_plan_mode_status_states(capsys) -> None:
    Renderer().plan_mode_status(True)
    on = capsys.readouterr().out
    assert "ON" in on
    Renderer().plan_mode_status(False)
    off = capsys.readouterr().out
    assert "OFF" in off


def test_ellipsize_truncates_long_commands() -> None:
    long_command = "echo " + " ".join(["arg"] * 100)
    result = _ellipsize(long_command)
    assert len(result) <= 100
    assert result.endswith("…")
    assert _ellipsize("short command") == "short command"


def test_ellipsize_collapses_newlines() -> None:
    assert _ellipsize("line one\nline two") == "line one line two"


def test_shorten_path_relative_inside_cwd() -> None:
    assert _shorten_path("src/app.py") == "src/app.py"


def test_shorten_path_home_abbreviation() -> None:
    import os

    home = os.path.expanduser("~")
    result = _shorten_path(f"{home}/projects/demo.txt")
    assert result.startswith("~/")
    assert not result.startswith(home)


def test_shorten_path_keeps_tail_when_truncating() -> None:
    deep = f"{'x/' * 80}target-file.txt"
    result = _shorten_path(deep)
    assert len(result) <= 100
    assert result.startswith("…")
    assert result.endswith("target-file.txt")


def test_banner_mentions_identity(capsys) -> None:
    Renderer(model="test-model").banner()
    out = capsys.readouterr().out
    assert "REFLEX CODE" in out
    assert "An autonomous coding agent." in out
    assert "test-model" in out
