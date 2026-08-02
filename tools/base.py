"""Abstract Tool interface.

Responsibilities:
- Defines the Tool abstract base class that every tool must implement.
- Requires: name (str), description (str), parameters (JSON Schema dict),
  and run(input) -> ToolResult.
- Tools are self-describing: they carry everything the LLM needs to call them.
"""
