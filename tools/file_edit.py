"""File edit tool.

Responsibilities:
- Applies targeted edits to an existing file using line-range or search-replace strategy.
- Never rewrites the whole file when a partial edit suffices.
- Returns a diff summary in the ToolResult metadata.
"""
