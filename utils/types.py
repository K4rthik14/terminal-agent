"""Shared type aliases and dataclasses.

Responsibilities:
- Single source of truth for all data shapes that cross module boundaries.
- Defines: Message, ToolCall, ToolResult, Plan, PlanStep, ApprovalDecision,
  StreamEvent, and common type aliases (MessageList, ToolName, etc.).
- Pure data definitions only. No methods with business logic.
- Imported by llm/, tools/, agent/, and cli/ — never imports from them.
"""
