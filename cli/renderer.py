"""Rich-based terminal output renderer.

Responsibilities:
- All terminal formatting lives here and nowhere else.
- Renders: streaming tokens, tool call previews, approval prompts,
  plan display, todo lists, errors, and final responses.
- Uses the `rich` library for panels, syntax highlighting, and spinners.
- Accepts structured data types from utils/types.py — never raw strings from agent logic.
"""

from rich.console import Console
from rich.panel import Panel

console = Console()


class Renderer:
    def banner(self) -> None:
        """Print the startup banner."""
        console.print(Panel(
            "[bold cyan]nanocode[/] — a terminal coding agent\n"
            "[dim]/plan toggles plan mode · ctrl-c / ctrl-d to quit[/]",
            border_style="cyan",
        ))

    def plan_mode_status(self, enabled: bool) -> None:
        status = "[green]on[/]" if enabled else "[yellow]off[/]"
        console.print(f"  Plan mode {status}")

    def error(self, message: str) -> None:
        console.print(f"[red]Error:[/] {message}")

    def info(self, message: str) -> None:
        console.print(f"[dim]{message}[/]")

    def goodbye(self) -> None:
        console.print("\n[dim]Goodbye![/]")
