"""File write tool.

Responsibilities:
- Creates a new file or overwrites an existing one at a given path.
- Flags overwrite operations for human approval via the Approver.
- Returns confirmation or a ToolError on failure.
"""

from typing import Any

from tools.base import Tool
from utils.types import ToolResult


class WriteFileTool(Tool):
    name = "write_file"
    description = "Write content to a file, creating or overwriting it."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to write."},
            "content": {"type": "string", "description": "Content to write."},
        },
        "required": ["path", "content"],
    }
    is_read_only = False

    def run(self, args: dict[str, Any]) -> ToolResult:
        try:
            with open(args["path"], "w", encoding="utf-8") as f:
                f.write(args["content"])
            return ToolResult(tool_call_id="", content=f"Wrote {args['path']}")
        except Exception as e:
            return ToolResult(tool_call_id="", content=f"Error writing file: {e}", is_error=True)
