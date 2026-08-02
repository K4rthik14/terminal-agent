"""File read tool.

Responsibilities:
- Reads the contents of a file at a given path.
- Enforces path safety rules (no traversal outside working directory).
- Returns file content as a ToolResult. Surfaces a ToolError on failure.
"""
