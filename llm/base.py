"""Abstract LLM client interface.

Responsibilities:
- Defines the LLMClient abstract base class with complete() and stream() methods.
- Defines canonical Message, ToolCall, and ToolDefinition dataclasses used
  across the entire system.
- No provider SDK is imported here. Concrete clients implement this interface.
"""
