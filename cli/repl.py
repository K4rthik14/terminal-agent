"""Interactive REPL loop.

Responsibilities:
- Manages the interactive session when no prompt is passed as a CLI argument.
- Handles multi-line input, input history, and graceful Ctrl+C / Ctrl+D exit.
- Calls agent.run() per turn and passes output to the Renderer.
- Does not contain any agent or LLM logic.
"""
