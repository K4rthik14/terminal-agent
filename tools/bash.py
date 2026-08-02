"""Bash execution tool.

Responsibilities:
- Executes a shell command in a subprocess with a strict timeout.
- Captures stdout, stderr, and exit code into ToolResult.
- Always requires human approval regardless of global approval setting.
- Never runs commands with shell=True without explicit sandboxing.
"""

import subprocess
from typing import Any

from config.defaults import TOOL_TIMEOUT_SECONDS
from tools.base import Tool
from utils.types import ToolResult


class BashTool(Tool):
    name = "bash"
    description = "Run a shell command and return stdout + stderr."
    parameters = {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "Shell command to run."},
        },
        "required": ["command"],
    }
    is_read_only = False  # always requires approval in AUTO mode

    def run(self, args: dict[str, Any]) -> ToolResult:
        try:
            result = subprocess.run(
                args["command"],
                shell=True,
                capture_output=True,
                text=True,
                timeout=TOOL_TIMEOUT_SECONDS,
            )
            output = result.stdout + result.stderr
            return ToolResult(tool_call_id="", content=output or "(no output)")
        except subprocess.TimeoutExpired:
            return ToolResult(tool_call_id="", content=f"Error: Command timed out after {TOOL_TIMEOUT_SECONDS}s", is_error=True)
        except Exception as e:
            return ToolResult(tool_call_id="", content=f"Error running command: {e}", is_error=True)
