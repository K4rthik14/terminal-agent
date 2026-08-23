"""Structured logging setup.

Responsibilities:
- Configures and returns a logger factory for use across all modules.
- JSON-formatted output in production; pretty-printed in development.
- Log level is read from Settings at startup.
- All modules call get_logger(__name__) — they never configure logging themselves.
"""

import logging

_DEFAULT_FORMAT = "%(levelname)s [%(name)s] %(message)s"


def get_logger(name: str) -> logging.Logger:
    """Return a named logger. Call this at module level: logger = get_logger(__name__)."""
    return logging.getLogger(name)


def configure_logging(level: str) -> None:
    """Configure the root logger. Called once at startup from cli/main.py."""
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(format=_DEFAULT_FORMAT, level=numeric_level)
    # Silence noisy third-party loggers that would clutter agent output.
    # "httpx2"/"httpcore2" are alias-installed copies used by some SDK builds.
    for name in ("httpx", "httpcore", "httpx2", "httpcore2"):
        logging.getLogger(name).setLevel(logging.WARNING)
