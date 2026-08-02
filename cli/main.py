"""CLI entry point.

Responsibilities:
- Parses CLI arguments: --model, --provider, --plan, --no-approval, --prompt, etc.
- Constructs the concrete LLMClient, ToolRegistry, and Settings instances.
- Injects dependencies into the Agent (no global state passed around).
- Starts the REPL if no --prompt is given; otherwise runs a single-shot turn.
"""
