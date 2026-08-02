"""Sub-agent tool.

Responsibilities:
- Spawns a child Agent instance with its own isolated AgentContext.
- Passes a delegated prompt and optional tool subset to the child.
- Blocks until the child agent completes and returns its final output as a ToolResult.
- The parent agent treats sub-agent output like any other tool result.
"""

from typing import Any, Callable

from tools.base import Tool
from utils.types import ToolResult


class SubAgentTool(Tool):
    name = "task"
    description = "Spawn a sub-agent with a fresh context to complete a task; returns its final answer."
    parameters = {
        "type": "object",
        "properties": {
            "description": {"type": "string", "description": "Short description."},
            "prompt": {"type": "string", "description": "Full instructions for the sub-agent."},
        },
        "required": ["description", "prompt"],
    }
    is_read_only = False

    def __init__(self, agent_factory: Callable) -> None:
        # agent_factory is a zero-arg callable that returns a fresh Agent instance.
        # Injected by cli/main.py to avoid circular imports.
        self._agent_factory = agent_factory

    def run(self, args: dict[str, Any]) -> ToolResult:
        try:
            agent = self._agent_factory()
            result = agent.run(args["prompt"])
            return ToolResult(tool_call_id="", content=result)
        except Exception as e:
            return ToolResult(tool_call_id="", content=f"Sub-agent error: {e}", is_error=True)
