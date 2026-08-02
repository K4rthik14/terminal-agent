"""Bash execution tool.

Responsibilities:
- Executes a shell command in a subprocess with a strict timeout.
- Captures stdout, stderr, and exit code into ToolResult.
- Always requires human approval regardless of global approval setting.
- Never runs commands with shell=True without explicit sandboxing.
"""
