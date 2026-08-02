"""Custom exception hierarchy.

Responsibilities:
- Defines all project-specific exceptions in one place.
- Hierarchy: AgentError (base) -> ToolError, LLMError, ApprovalDeniedError, ConfigError.
- Enables precise except clauses at each layer without catching overly broad exceptions.
- No logic — exception class definitions only.
"""
