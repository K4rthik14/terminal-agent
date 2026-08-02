"""Todo management tool.

Responsibilities:
- Provides in-memory todo list operations: add, complete, delete, list.
- State lives in AgentContext, not in this module — the tool reads and writes context.
- Useful for the agent to track multi-step task progress across turns.
"""
