"""Tool registry and discovery.

Responsibilities:
- Provides ToolRegistry: the single authoritative map of tool name -> Tool instance.
- Tools register themselves by being imported (explicit registration, not magic).
- Exposes get(name), all(), and as_definitions() for sending schemas to the LLM.
- Raises a clear error on duplicate registration or unknown tool lookup.
"""
