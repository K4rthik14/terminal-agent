"""Rich-based terminal output renderer.

Responsibilities:
- Renders concise, user-visible progress states with a consistent visual
  language: ⠋ activity (cyan), ✓ success (green), ✗ failure (red), dim meta.
- Renders compact one-line tool activity without exposing raw arguments.
- Keeps terminal output focused on actions and outcomes.
"""

from __future__ import annotations

import os
import time
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _package_version
from typing import Any

from rich.console import Console

console = Console(highlight=False)

_FALLBACK_VERSION = "0.1.0"
_SUMMARY_LIMIT = 100

_TOOL_LABELS = {
    "read_file": "Reading",
    "write_file": "Writing",
    "edit_file": "Editing",
    "bash": "Running",
    "todo_write": "Updating todos",
    "web_search": "Searching",
    "web_fetch": "Fetching",
    "task": "Delegating",
}


def _resolve_version() -> str:
    """Return the installed package version, falling back to a known default."""
    try:
        return _package_version("terminal-agent")
    except PackageNotFoundError:
        return _FALLBACK_VERSION


def _ellipsize(text: str, limit: int = _SUMMARY_LIMIT) -> str:
    """Collapse whitespace and truncate with an ellipsis, keeping the head."""
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    return f"{text[: limit - 1]}…"


def _shorten_path(path: str, limit: int = _SUMMARY_LIMIT) -> str:
    """Relative path inside cwd, otherwise ~-abbreviated absolute; keep tail."""
    if not path:
        return ""
    candidate = os.path.relpath(path, os.getcwd())
    if candidate.startswith(".."):
        # A relative climb ("../../x") is harder to read than the real location.
        home = os.path.expanduser("~")
        candidate = f"~{path[len(home):]}" if path.startswith(home) else path
    if len(candidate) > limit:
        candidate = f"…{candidate[-(limit - 1):]}"
    return candidate


class Renderer:
    """Compact terminal renderer for interactive and single-shot sessions."""

    def __init__(
        self, model: str | None = None, plan_mode: bool = False, approval_mode: str = "auto"
    ) -> None:
        self._model = model or "AI coding agent"
        self._plan_mode = plan_mode
        self._approval_mode = approval_mode

    def banner(self, model: str | None = None) -> None:
        """Render a concise startup identity line."""
        model_label = model or self._model
        cwd = os.path.basename(os.getcwd()) or os.getcwd()

        console.print(
            f"[bold cyan]Trace Code[/] [dim]v{_resolve_version()} · {model_label} · {cwd}[/]"
        )
        console.print(
            f"[green]✓ Ready[/] [dim]· plan {'on' if self._plan_mode else 'off'}"
            f" · approval {self._approval_mode}[/]"
        )
        console.print("[dim]/plan toggle planning · Ctrl+C interrupt · Ctrl+D exit[/]\n")

    def thinking(self) -> None:
        console.print("[cyan]⠋[/] [dim]Thinking…[/]")

    def executing(self, tool_name: str, args: dict[str, Any]) -> float:
        """Render one compact activity line and return its start time."""
        summary = self._tool_summary(tool_name, args)
        label = _TOOL_LABELS.get(tool_name, "Running")
        line = f"[cyan]⠋ {label}[/]"
        if summary:
            line += f" [dim]· {summary}[/]"
        console.print(line)
        return time.monotonic()

    def completed_tool(self, tool_name: str, success: bool, started_at: float) -> None:
        duration = time.monotonic() - started_at
        mark, label, color = ("✓", "Done", "green") if success else ("✗", "Failed", "red")
        console.print(f"[{color}]{mark} {label}[/] [dim]({duration:.1f}s)[/]\n")

    def completed(self) -> None:
        console.print("[green]✓ Completed[/]\n")

    def plan_mode_status(self, enabled: bool) -> None:
        state = "[magenta]ON[/]" if enabled else "[dim]OFF[/]"
        console.print(f"Plan mode: {state}")

    def error(self, message: str) -> None:
        console.print(f"[red]✗ Error:[/] {message}")

    def info(self, message: str) -> None:
        console.print(f"[dim]{message}[/]")

    def goodbye(self) -> None:
        console.print("\n[dim]Goodbye![/]")

    @staticmethod
    def _tool_summary(tool_name: str, args: dict[str, Any]) -> str:
        if tool_name in {"write_file", "edit_file", "read_file"}:
            return _shorten_path(str(args.get("path", "")))
        if tool_name == "bash":
            return _ellipsize(str(args.get("command", "")))
        if tool_name == "web_search":
            return _ellipsize(str(args.get("query", "")))
        if tool_name == "web_fetch":
            return _ellipsize(str(args.get("url", "")))
        if tool_name == "task":
            return _ellipsize(str(args.get("description", "")))
        return ""
