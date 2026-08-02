"""Human approval gate.

Responsibilities:
- Accepts a ToolCall and presents it to the user for review.
- Blocks execution until the user responds: approved, rejected, or modified.
- Returns an ApprovalDecision that the Executor acts on.
- Approval policy (always, never, per-tool) is read from settings, not hardcoded here.
"""
