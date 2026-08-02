"""Human approval gate.

Responsibilities:
- Accepts a ToolCall and presents it to the user for review.
- Blocks execution until the user responds: approved, rejected, or modified.
- Returns an ApprovalDecision that the Executor acts on.
- Approval policy (always, never, per-tool) is read from settings, not hardcoded here.
"""

import json
from utils.types import ToolCall, ApprovalDecision, ApprovalMode


class Approver:
    def __init__(self, mode: ApprovalMode) -> None:
        self._mode = mode

    def requires_approval(self, is_read_only: bool) -> bool:
        if self._mode == ApprovalMode.NEVER:
            return False
        if self._mode == ApprovalMode.ALWAYS:
            return True
        # AUTO: only non-read-only tools require approval
        return not is_read_only

    def request(self, tool_call: ToolCall, args: dict) -> ApprovalDecision:
        """Block until user approves or rejects. Returns ApprovalDecision."""
        try:
            answer = input(f"\n  {tool_call.name}({json.dumps(args, ensure_ascii=False)}) [y/n] ")
            if answer.strip().lower() == "y":
                return ApprovalDecision.APPROVED
            return ApprovalDecision.REJECTED
        except (EOFError, KeyboardInterrupt):
            return ApprovalDecision.REJECTED
