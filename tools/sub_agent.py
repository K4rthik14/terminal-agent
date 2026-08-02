"""Sub-agent tool.

Responsibilities:
- Spawns a child Agent instance with its own isolated AgentContext.
- Passes a delegated prompt and optional tool subset to the child.
- Blocks until the child agent completes and returns its final output as a ToolResult.
- The parent agent treats sub-agent output like any other tool result.
"""
