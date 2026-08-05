"""Human approval gate.

Responsibilities:
- Accepts a ToolCall and presents it to the user for review.
- Blocks execution until the user responds: approved, rejected, or modified.
- Returns an ApprovalDecision that the Executor acts on.
- Approval policy (always, never, per-tool) is read from settings, not hardcoded here.
"""

import os
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
            summary = self._summary(tool_call.name, args)
            prompt = f"\n  Approve {tool_call.name}"
            if summary:
                prompt += f" · {summary}"
            answer = input(f"{prompt} [y/n] ")
            if answer.strip().lower() == "y":
                return ApprovalDecision.APPROVED
            return ApprovalDecision.REJECTED
        except (EOFError, KeyboardInterrupt):
            return ApprovalDecision.REJECTED

    @staticmethod
    def _summary(tool_name: str, args: dict) -> str:
        if tool_name in {"write_file", "edit_file", "read_file"}:
            path = str(args.get("path", ""))
            return os.path.relpath(path, os.getcwd()) if path else ""
        if tool_name == "bash":
            command = str(args.get("command", ""))
            return command if len(command) <= 100 else f"{command[:97]}..."
        return ""
