"""Structured logging setup.

Responsibilities:
- Configures and returns a logger factory for use across all modules.
- JSON-formatted output in production; pretty-printed in development.
- Log level is read from Settings at startup.
- All modules call get_logger(__name__) — they never configure logging themselves.
"""
