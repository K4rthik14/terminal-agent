"""Hardcoded defaults and system constants.

Responsibilities:
- Defines constants that are never user-configurable: MAX_TOOL_RETRIES,
  TOOL_TIMEOUT_SECONDS, RESERVED_TOOL_NAMES, PHASE_FLAGS, etc.
- Imported by modules that need stable system-level values.
- No logic, no classes — constants only.
"""

MAX_TOOL_RETRIES: int = 3
TOOL_TIMEOUT_SECONDS: int = 30
MAX_WEB_CONTENT_LENGTH: int = 5000
MAX_ITERATIONS: int = 50
MAX_TOOL_CALLS: int = 100
MAX_EXECUTION_TIME_SECONDS: float = 300.0
MAX_LLM_RETRIES: int = 2
LLM_RETRY_BACKOFF_SECONDS: float = 0.5
MAX_CONTEXT_MESSAGES: int = 24
OPENROUTER_MODEL: str = "poolside/laguna-s-2.1:free"
OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
DEFAULT_MODEL: str = OPENROUTER_MODEL
DEFAULT_BASE_URL: str = OPENROUTER_BASE_URL
DEFAULT_PROVIDER: str = "openai"
DEFAULT_LOG_LEVEL: str = "info"
DEFAULT_APPROVAL_MODE: str = "auto"
DEFAULT_VERIFICATION_COMMAND: str = ""
DEFAULT_VERIFICATION_TIMEOUT_SECONDS: int = 30
RESERVED_TOOL_NAMES: frozenset[str] = frozenset({"task"})
AGENT_INSTRUCTIONS_FILE: str = "NANOCODE.md"
DEFAULT_RLM_ENABLED: bool = False
