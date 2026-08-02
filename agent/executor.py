"""Tool dispatch and execution.

Responsibilities:
- Receives a ToolCall from the LLM response.
- Resolves the tool by name from the ToolRegistry.
- Invokes the Approver if the tool or global config requires human approval.
- Runs the tool and returns a ToolResult.
- Handles tool-level errors without crashing the agent loop.
"""
