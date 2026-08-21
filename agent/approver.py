"""Human approval gate.

Responsibilities:
- Accepts a ToolCall and presents it to the user for review.
- Blocks execution until the user responds: approved, rejected, or modified.
- Returns an ApprovalDecision that the Executor acts on.
- Approval policy (always, never, per-tool) is read from settings, not hardcoded here.
"""

import os

from utils.types import ApprovalDecision, ApprovalMode, ToolCall

_YES_ANSWERS = frozenset({"y", "yes"})
_NO_ANSWERS = frozenset({"n", "no", ""})  # empty input defaults to deny ([y/N])

# Used only for prompt labeling so users can gauge consequence at a glance.
# Permission decisions never depend on this set — they come from
# requires_approval(), which is driven by each tool's is_read_only flag.
_READ_ONLY_TOOLS = frozenset({"read_file", "todo_write", "web_search", "web_fetch"})


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
        """Block until the user approves or rejects. Denial is always the safe default."""
        scope = "read-only" if tool_call.name in _READ_ONLY_TOOLS else "may modify your system"
        summary = self._summary(tool_call.name, args)
        prompt = f"\n  ⚠ Approval needed · {tool_call.name} ({scope})"
        if summary:
            prompt += f"\n    {summary}"
        prompt += "\n    Allow? [y/N] "
        try:
            while True:
                answer = input(prompt).strip().lower()
                if answer in _YES_ANSWERS:
                    return ApprovalDecision.APPROVED
                if answer in _NO_ANSWERS:
                    print("  ✗ Denied — nothing was executed.")
                    return ApprovalDecision.REJECTED
                print("  Please answer y (allow) or n (deny).")
        except (EOFError, KeyboardInterrupt):
            print("\n  ✗ Denied — nothing was executed.")
            return ApprovalDecision.REJECTED

    @staticmethod
    def _summary(tool_name: str, args: dict) -> str:
        if tool_name in {"write_file", "edit_file", "read_file"}:
            path = str(args.get("path", ""))
            return os.path.relpath(path, os.getcwd()) if path else ""
        if tool_name == "bash":
            command = str(args.get("command", ""))
            return command if len(command) <= 100 else f"{command[:97]}..."
        if tool_name == "web_search":
            query = str(args.get("query", ""))
            return query if len(query) <= 100 else f"{query[:97]}..."
        if tool_name == "web_fetch":
            url = str(args.get("url", ""))
            return url if len(url) <= 100 else f"{url[:97]}..."
        if tool_name == "task":
            description = str(args.get("description", ""))
            return description if len(description) <= 100 else f"{description[:97]}..."
        return ""
