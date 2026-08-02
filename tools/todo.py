"""Todo management tool.

Responsibilities:
- Provides in-memory todo list operations: add, complete, delete, list.
- State lives in AgentContext, not in this module — the tool reads and writes context.
- Useful for the agent to track multi-step task progress across turns.
"""

from typing import Any

from tools.base import Tool
from utils.types import ToolResult


class TodoWriteTool(Tool):
    name = "todo_write"
    description = "Write the current task list. Replaces the whole list each call."
    parameters = {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "content": {"type": "string"},
                        "status": {"type": "string", "enum": ["pending", "in_progress", "done"]},
                    },
                    "required": ["content", "status"],
                },
            },
        },
        "required": ["items"],
    }
    is_read_only = True

    def __init__(self) -> None:
        self.items: list[dict[str, str]] = []

    def run(self, args: dict[str, Any]) -> ToolResult:
        self.items = args["items"]
        marks = {"pending": " ", "in_progress": "~", "done": "x"}
        lines = [f"[{marks[item['status']]}] {item['content']}" for item in self.items]
        return ToolResult(tool_call_id="", content="\n".join(lines))
