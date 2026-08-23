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
_INFO_MIN_WIDTH = 26  # narrowest useful side-by-side info column

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
        """Render the startup header: wordmark, tagline, session status."""
        model_label = model or self._model
        version = f"v{_resolve_version()}"
        mode = f"plan {'on' if self._plan_mode else 'off'} · approval {self._approval_mode}"
        hint = "/plan toggle planning · Ctrl+C interrupt · Ctrl+D exit"

        if console.width >= _WORDMARK_WIDTH + _META_GAP and console.is_terminal:
            self._wide_banner(model_label, version, mode, hint)
        else:
            self._compact_banner(model_label, version, mode, hint)

    def _session_info(self, model: str, version: str, mode: str) -> list[Text]:
        """Session facts shown beside or below the wordmark, in order."""
        return [
            Text("An autonomous coding agent."),
            Text(model, style="dim"),
            Text(_display_cwd(), style="dim"),
            Text(f"{mode} · {version}", style="dim"),
        ]

    def _wide_banner(self, model: str, version: str, mode: str, hint: str) -> None:
        """Gradient REFLEX CODE wordmark with dim session info."""
        art = _wordmark_lines()
        art_width = max(len(row.plain) for row in art)
        info_rows = self._session_info(model, version, mode)
        side_by_side = console.width >= art_width + _META_GAP + _INFO_MIN_WIDTH

        if side_by_side:
            info: dict[int, Text] = {
                1: info_rows[0],
                3: info_rows[1],
                4: info_rows[2],
                5: info_rows[3],
            }
            for i, row in enumerate(art):
                row.pad_right(art_width + _META_GAP - len(row.plain))
                if i in info:
                    row.append_text(info[i])
                console.print(row)
            # Indent the hint under the info column only when it fits.
            if console.width >= art_width + _META_GAP + len(hint):
                hint_line = Text(hint, style="dim")
                hint_line.pad_left(art_width + _META_GAP)
                console.print(hint_line)
            else:
                console.print(Text(hint, style="dim"))
            console.print()
        else:
            # Medium terminals: full wordmark, session info stacked below.
            for row in art:
                console.print(row)
            console.print()
            for line in info_rows:
                console.print(line)
            console.print(Text(hint, style="dim"))
            console.print()

    def _compact_banner(self, model: str, version: str, mode: str, hint: str) -> None:
        """Narrow-terminal fallback: plain identity block, no wordmark."""
        console.print(f"[bold cyan]REFLEX CODE[/] [dim]{version}[/]")
        console.print("An autonomous coding agent.")
        console.print(model)
        console.print(f"[dim]{_display_cwd()} · {mode}[/]")
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
