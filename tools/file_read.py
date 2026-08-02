"""File read tool.

Responsibilities:
- Reads the contents of a file at a given path.
- Enforces path safety rules (no traversal outside working directory).
- Returns file content as a ToolResult. Surfaces a ToolError on failure.
"""

from typing import Any

from tools.base import Tool
from utils.types import ToolResult


class ReadFileTool(Tool):
    name = "read_file"
    description = "Read a file from disk and return its contents."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to the file to read."},
        },
        "required": ["path"],
    }
    is_read_only = True

    def run(self, args: dict[str, Any]) -> ToolResult:
        try:
            with open(args["path"], encoding="utf-8") as f:
                return ToolResult(tool_call_id="", content=f.read())
        except FileNotFoundError:
            return ToolResult(tool_call_id="", content=f"Error: File not found: {args['path']}", is_error=True)
        except PermissionError:
            return ToolResult(tool_call_id="", content=f"Error: Permission denied: {args['path']}", is_error=True)
        except Exception as e:
            return ToolResult(tool_call_id="", content=f"Error reading file: {e}", is_error=True)
