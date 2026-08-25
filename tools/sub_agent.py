"""Sub-agent tool.

Responsibilities:
- Spawns a child Agent instance with its own isolated AgentContext.
- Passes a delegated prompt and optional tool subset to the child.
- Blocks until the child agent completes and returns its final output as a ToolResult.
- The parent agent treats sub-agent output like any other tool result.
- Caps delegation nesting so recursive task() calls cannot become unbounded.
"""

from collections.abc import Callable
from contextvars import ContextVar
from typing import Any

from config.defaults import MAX_SUBAGENT_DEPTH
from tools.base import Tool
from utils.types import ToolResult

# Current nesting depth of executing sub-agents. The top-level agent runs at 0;
# each delegated child runs at parent depth + 1.
SUBAGENT_DEPTH: ContextVar[int] = ContextVar("subagent_depth", default=0)


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

    def __init__(self, agent_factory: Callable[[], Any]) -> None:
        # agent_factory is a zero-arg callable that returns a fresh Agent instance.
        # Injected by cli/main.py to avoid circular imports.
        self._agent_factory = agent_factory

    def run(self, args: dict[str, Any]) -> ToolResult:
        depth = SUBAGENT_DEPTH.get()
        if depth >= MAX_SUBAGENT_DEPTH:
            return ToolResult(
                tool_call_id="",
                content=(
                    f"Error: delegation depth limit reached ({MAX_SUBAGENT_DEPTH}). "
                    "Complete this task directly instead of delegating further."
                ),
                is_error=True,
            )
        try:
            agent = self._agent_factory()
        except Exception as e:
            return ToolResult(tool_call_id="", content=f"Sub-agent error: {e}", is_error=True)

        child_token = SUBAGENT_DEPTH.set(depth + 1)
        try:
            result = agent.run(args["prompt"])
            return ToolResult(tool_call_id="", content=result)
        except Exception as e:
            return ToolResult(tool_call_id="", content=f"Sub-agent error: {e}", is_error=True)
        finally:
            SUBAGENT_DEPTH.reset(child_token)
