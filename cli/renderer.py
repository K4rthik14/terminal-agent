"""Rich-based terminal output renderer.

Responsibilities:
- Renders concise, user-visible progress states.
- Renders compact tool execution cards without exposing raw arguments.
- Keeps terminal output focused on actions and outcomes.
"""

from __future__ import annotations

import os
import time
from typing import Any

from rich.console import Console
console = Console()


class Renderer:
    """Minimal terminal renderer for interactive and single-shot sessions."""

    def __init__(self, model: str | None = None, plan_mode: bool = False, approval_mode: str = "auto") -> None:
        self._model = model or "AI coding agent"
        self._plan_mode = plan_mode
        self._approval_mode = approval_mode

    def banner(self, model: str | None = None) -> None:
        """Print a compact startup header."""
        model_label = model or self._model
        console.print(f"[bold cyan]nanocode[/]   [dim]{model_label}[/] • [dim]{os.getcwd()}[/]")
        console.print("[dim]────────────────────────────────────────────────────────────[/]")
        plan = "ON" if self._plan_mode else "OFF"
        console.print(f"[green]✓ Ready[/]  [dim]Plan: {plan}   Approval: {self._approval_mode.upper()}[/]\n")

    def thinking(self) -> None:
        console.print("[cyan]⠋ Thinking...[/]")

    def executing(self, tool_name: str, args: dict[str, Any]) -> float:
        """Render a concise action state and return its start time."""
        summary = self._tool_summary(tool_name, args)
        state = {
            "write_file": "Creating File",
            "edit_file": "Editing File",
            "bash": "Running",
            "read_file": "Reading File",
            "web_search": "Searching Web",
            "web_fetch": "Fetching Page",
            "task": "Delegating",
        }.get(tool_name, "Executing")
        console.print(f"[cyan]⠋ {state}...[/]")
        icon = {
            "write_file": "📝",
            "edit_file": "📝",
            "bash": "⚙",
            "read_file": "📖",
            "web_search": "🔎",
            "web_fetch": "🌐",
            "task": "↗",
        }.get(tool_name, "•")
        console.print(f"[bold cyan]{icon} {tool_name}[/]")
        if summary:
            console.print(f"   [dim]{summary}[/]")
        return time.monotonic()

    def completed_tool(self, tool_name: str, success: bool, started_at: float) -> None:
        duration = time.monotonic() - started_at
        if tool_name == "bash" and success:
            label = "Passed"
        else:
            label = "Success" if success else "Failed"
        color = "green" if success else "red"
        console.print(f"[green]✓[/] [{color}]{label}[/] [dim]({duration:.1f}s)[/]\n")

    def completed(self) -> None:
        console.print("[green]✓ Completed[/]\n")

    def plan_mode_status(self, enabled: bool) -> None:
        status = "ON" if enabled else "OFF"
        console.print(f"[dim]Plan: {status}[/]")

    def error(self, message: str) -> None:
        console.print(f"[red]Error:[/] {message}")

    def info(self, message: str) -> None:
        console.print(f"[dim]{message}[/]")

    def goodbye(self) -> None:
        console.print("\n[dim]Goodbye![/]")

    @staticmethod
    def _tool_summary(tool_name: str, args: dict[str, Any]) -> str:
        if tool_name in {"write_file", "edit_file", "read_file"}:
            path = str(args.get("path", ""))
            return os.path.relpath(path, os.getcwd()) if path else ""
        if tool_name == "bash":
            command = str(args.get("command", ""))
            return command if len(command) <= 120 else f"{command[:117]}..."
        if tool_name == "web_search":
            return str(args.get("query", ""))
        if tool_name == "web_fetch":
            return str(args.get("url", ""))
        if tool_name == "task":
            return str(args.get("description", ""))
        return ""
