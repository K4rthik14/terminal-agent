"""File edit tool.

Responsibilities:
- Applies targeted edits to an existing file using line-range or search-replace strategy.
- Never rewrites the whole file when a partial edit suffices.
- Returns a diff summary in the ToolResult metadata.
"""

from typing import Any

from tools.base import Tool
from utils.types import ToolResult


class EditFileTool(Tool):
    name = "edit_file"
    description = "Replace an exact string in a file with a new string."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to the file."},
            "old_string": {"type": "string", "description": "Exact string to replace."},
            "new_string": {"type": "string", "description": "Replacement string."},
        },
        "required": ["path", "old_string", "new_string"],
    }
    is_read_only = False

    def run(self, args: dict[str, Any]) -> ToolResult:
        try:
            with open(args["path"], encoding="utf-8") as f:
                content = f.read()
            if args["old_string"] not in content:
                return ToolResult(tool_call_id="", content=f"Error: old_string not found in {args['path']}", is_error=True)
            updated = content.replace(args["old_string"], args["new_string"], 1)
            with open(args["path"], "w", encoding="utf-8") as f:
                f.write(updated)
            return ToolResult(tool_call_id="", content=f"Edited {args['path']}")
        except FileNotFoundError:
            return ToolResult(tool_call_id="", content=f"Error: File not found: {args['path']}", is_error=True)
        except Exception as e:
            return ToolResult(tool_call_id="", content=f"Error editing file: {e}", is_error=True)
