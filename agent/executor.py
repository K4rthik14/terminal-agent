"""Tool dispatch and execution.

Responsibilities:
- Receives a ToolCall from the LLM response.
- Resolves the tool by name from the ToolRegistry.
- Invokes the Approver if the tool or global config requires human approval.
- Runs the tool and returns a ToolResult.
- Handles tool-level errors without crashing the agent loop.
"""

import json
from utils.types import ToolCall, ToolResult, ApprovalDecision
from utils.errors import ToolNotFoundError
from utils.logging import get_logger
from tools.registry import ToolRegistry
from agent.approver import Approver

logger = get_logger(__name__)


class Executor:
    def __init__(self, registry: ToolRegistry, approver: Approver, plan_mode: bool = False) -> None:
        self._registry = registry
        self._approver = approver
        self._plan_mode = plan_mode

    def run(self, tool_call: ToolCall) -> ToolResult:
        """Resolve, approve, and execute a single ToolCall. Never raises."""
        # Parse arguments
        try:
            args = json.loads(tool_call.arguments or "{}")
        except json.JSONDecodeError as e:
            return ToolResult(tool_call_id=tool_call.id, content=f"Error: invalid JSON arguments: {e}", is_error=True)

        # Resolve tool
        try:
            tool = self._registry.get(tool_call.name)
        except ToolNotFoundError:
            return ToolResult(tool_call_id=tool_call.id, content=f"Error: unknown tool {tool_call.name!r}", is_error=True)

        # Plan mode: block write tools
        if self._plan_mode and not tool.is_read_only:
            return ToolResult(
                tool_call_id=tool_call.id,
                content="Plan mode is on: write tools are disabled. Present a plan and ask the user to approve it.",
                is_error=False,
            )

        # Approval gate
        if self._approver.requires_approval(tool.is_read_only):
            decision = self._approver.request(tool_call, args)
            if decision == ApprovalDecision.REJECTED:
                return ToolResult(tool_call_id=tool_call.id, content="User denied the tool call.", is_error=False)

        # Execute
        logger.debug("Running tool %s with args %s", tool_call.name, args)
        try:
            result = tool.run(args)
            # Stamp the real tool_call_id (tools return "" as placeholder)
            result.tool_call_id = tool_call.id
            return result
        except Exception as e:
            logger.exception("Unexpected error in tool %s", tool_call.name)
            return ToolResult(tool_call_id=tool_call.id, content=f"Error: {e}", is_error=True)
