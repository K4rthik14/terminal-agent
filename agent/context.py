"""Agent session context — the single source of mutable session state.

Responsibilities:
- Carries all state for one agent session: message history, tool results,
  active plan, token usage, and metadata.
- Passed by reference through the agent turn. Never stored globally.
- Not persisted in Phase 1; designed to be serializable for Phase 2 memory support.
"""
