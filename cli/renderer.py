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

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

console = Console(highlight=False)

_FALLBACK_VERSION = "0.1.0"
# Distribution names that may carry the version metadata, newest first.
_DISTRIBUTION_NAMES = ("reflex-code", "terminal-agent")
_SUMMARY_LIMIT = 100

# Startup wordmark (block font, single line). Rendered with a top-to-bottom
# gradient; session info sits in a dim column to its right when there is room,
# stacks beneath it on medium terminals, and is replaced by a compact header
# when the terminal is too narrow for the art itself.
_WORDMARK = (
    "██████╗ ███████╗███████╗██╗     ███████╗██╗  ██╗  ██████╗ ██████╗ ██████╗ ███████╗",
    "██╔══██╗██╔════╝██╔════╝██║     ██╔════╝╚██╗██╔╝ ██╔════╝██╔═══██╗██╔══██╗██╔════╝",
    "██████╔╝█████╗  █████╗  ██║     █████╗   ╚███╔╝  ██║     ██║   ██║██║  ██║█████╗  ",
    "██╔══██╗██╔══╝  ██╔══╝  ██║     ██╔══╝   ██╔██╗  ██║     ██║   ██║██║  ██║██╔══╝  ",
    "██║  ██║███████╗██║     ███████╗███████╗██╔╝ ██╗ ╚██████╗╚██████╔╝██████╔╝███████╗",
    "╚═╝  ╚═╝╚══════╝╚═╝     ╚══════╝╚══════╝╚═╝  ╚═╝  ╚═════╝ ╚═════╝ ╚═════╝ ╚══════╝",
)
_WORDMARK_WIDTH = max(len(line.rstrip()) for line in _WORDMARK)
_GRADIENT_TOP = (0x22, 0xD3, 0xEE)  # cyan
_GRADIENT_BOTTOM = (0xA8, 0x55, 0xF7)  # violet
_META_GAP = 2  # blank columns between the wordmark and the info column
_META_VALUE_LIMIT = 46  # max characters for a metadata panel value

_TOOL_LABELS = {
    "read_file": "Read file",
    "write_file": "Write file",
    "edit_file": "Edit file",
    "bash": "Run command",
    "todo_write": "Update todos",
    "web_search": "Web search",
    "web_fetch": "Web fetch",
    "task": "Sub-agent",
}


def _resolve_version() -> str:
    """Return the installed package version, falling back to a known default."""
    for distribution in _DISTRIBUTION_NAMES:
        try:
            return _package_version(distribution)
        except PackageNotFoundError:
            continue
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


def _display_cwd(limit: int = 48) -> str:
    """~-abbreviated current working directory, tail-kept when long."""
    cwd = os.getcwd()
    home = os.path.expanduser("~")
    candidate = f"~{cwd[len(home):]}" if cwd.startswith(home) else cwd
    if len(candidate) > limit:
        candidate = f"…{candidate[-(limit - 1):]}"
    return candidate


def _clip(text: str, limit: int = _META_VALUE_LIMIT) -> str:
    """Truncate long values (model ids, paths) keeping the head, with ellipsis."""
    if len(text) <= limit:
        return text
    return f"{text[: limit - 1]}…"


def _gradient_hex(fraction: float) -> str:
    """Interpolate between the gradient anchors; fraction 0=top, 1=bottom."""
    top, bottom = _GRADIENT_TOP, _GRADIENT_BOTTOM
    channels = (
        round(a + (b - a) * fraction) for a, b in zip(top, bottom, strict=True)
    )
    return "#{:02x}{:02x}{:02x}".format(*channels)


def _wordmark_lines() -> list[Text]:
    """The wordmark as Rich Text rows, one gradient step per row."""
    last = len(_WORDMARK) - 1
    return [
        Text(line.rstrip(), style=f"bold {_gradient_hex(i / last)}")
        for i, line in enumerate(_WORDMARK)
    ]


class Renderer:
    """Compact terminal renderer for interactive and single-shot sessions."""

    def __init__(
        self, model: str | None = None, plan_mode: bool = False, approval_mode: str = "auto"
    ) -> None:
        self._model = model or "AI coding agent"
        self._plan_mode = plan_mode
        self._approval_mode = approval_mode
        self._active_activity: tuple[str, str] | None = None

    def banner(self, model: str | None = None) -> None:
        """Render the startup header: wordmark, tagline, metadata panel."""
        model_label = model or self._model
        version = f"v{_resolve_version()}"
        mode_label = "plan" if self._plan_mode else "normal"
        hint = "/plan toggle planning · Ctrl+C interrupt · Ctrl+D exit"

        if console.width >= _WORDMARK_WIDTH + _META_GAP and console.is_terminal:
            self._wide_banner(model_label, version, mode_label, hint)
        else:
            self._compact_banner(model_label, version, mode_label, hint)

    def _metadata_panel(self, model: str, mode_label: str) -> Panel:
        """Compact rounded panel: active model, workdir, mode, approval, status."""
        mode_value = Text("plan", style="bold magenta") if self._plan_mode else Text("normal")
        mode_value.append(f" · approval {self._approval_mode}", style="dim")

        grid = Table.grid(padding=(0, 2))
        grid.add_column(style="bold dim", justify="left")
        grid.add_column()
        grid.add_row("MODEL", Text(_clip(model)))
        grid.add_row("WORKDIR", Text(_display_cwd(_META_VALUE_LIMIT)))
        grid.add_row("MODE", mode_value)
        grid.add_row("STATUS", Text("● ready", style="green"))
        return Panel(
            grid,
            box=box.ROUNDED,
            border_style="dim",
            padding=(0, 1),
            width=_META_VALUE_LIMIT + 16,
        )

    def _wide_banner(self, model: str, version: str, mode_label: str, hint: str) -> None:
        """Gradient REFLEX CODE wordmark over a compact metadata panel."""
        for row in _wordmark_lines():
            console.print(row)
        console.print()

        tagline = Text("An autonomous coding agent.")
        tagline.append(f" · {version}", style="dim")
        console.print(tagline)

        panel_width = min(_META_VALUE_LIMIT + 16, max(console.width - 2, 20))
        grid = self._metadata_panel(model, mode_label)
        grid.width = panel_width
        console.print(grid)

        console.print(Text(hint, style="dim"))
        console.print()

    def _compact_banner(self, model: str, version: str, mode_label: str, hint: str) -> None:
        """Narrow-terminal fallback: plain identity block, no wordmark."""
        console.print(f"[bold cyan]REFLEX CODE[/] [dim]{version}[/]")
        console.print("An autonomous coding agent.")
        console.print(_clip(model))
        console.print(f"[dim]{_display_cwd()}[/]")
        console.print(f"{mode_label} [dim]· approval {self._approval_mode}[/]", end=" ")
        console.print("[green]· ● ready[/]")
        console.print(f"[dim]{hint}[/]\n")

    def thinking(self) -> None:
        console.print("[cyan]⠋[/] [dim]Thinking…[/]")

    def executing(self, tool_name: str, args: dict[str, Any]) -> float:
        """Render one compact activity line and return its start time."""
        summary = self._tool_summary(tool_name, args)
        label = _TOOL_LABELS.get(tool_name, "Working")
        line = f"[cyan]⠋ {label}[/]"
        if summary:
            line += f" [dim]· {summary}[/]"
        console.print(line)
        self._active_activity = (label, summary)
        return time.monotonic()

    def completed_tool(self, tool_name: str, success: bool, started_at: float) -> None:
        duration = time.monotonic() - started_at
        label, summary = self._active_activity or (_TOOL_LABELS.get(tool_name, "Done"), "")
        self._active_activity = None
        mark, color = ("✓", "green") if success else ("✗", "red")
        line = f"[{color}]{mark} {label}[/]" if success else f"[{color}]✗ {label} failed[/]"
        if summary:
            line += f" [dim]· {summary}[/]"
        line += f" [dim]({duration:.1f}s)[/]"
        console.print(line + "\n")

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
