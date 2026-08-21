"""Pydantic settings model.

Responsibilities:
- Defines the Settings class using pydantic-settings BaseSettings.
- Reads configuration from environment variables and .env file.
- Fields include: model, provider, api_key, max_tokens, approval_mode, log_level.
- Single source of truth for all user-configurable values.
- CLI flag overrides are applied here after initial load.
"""

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from config.defaults import (
    DEFAULT_APPROVAL_MODE,
    DEFAULT_BASE_URL,
    DEFAULT_LOG_LEVEL,
    DEFAULT_MODEL,
    DEFAULT_PROVIDER,
    DEFAULT_RLM_ENABLED,
    DEFAULT_VERIFICATION_COMMAND,
    DEFAULT_VERIFICATION_TIMEOUT_SECONDS,
    MAX_CONTEXT_MESSAGES,
    MAX_EXECUTION_TIME_SECONDS,
    MAX_ITERATIONS,
    MAX_TOOL_CALLS,
    MAX_WEB_CONTENT_LENGTH,
)

# Accepted environment variables for the LLM provider API key, in priority order.
# Single source of truth: used by the Settings field alias and by user-facing
# configuration guidance in the CLI.
API_KEY_ENV_VARS: tuple[str, str] = ("AGENT_API_KEY", "OPENROUTER_API_KEY")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AGENT_", env_file=".env", extra="ignore")

    provider: str = DEFAULT_PROVIDER
    base_url: str = DEFAULT_BASE_URL
    model: str = DEFAULT_MODEL
    api_key: str = Field(
        default="",
        validation_alias=AliasChoices(*API_KEY_ENV_VARS),
        repr=False,
    )  # Never store or print API keys; supports both generic and OpenRouter names.
    max_tokens: int = 4096
    max_iterations: int = MAX_ITERATIONS
    max_tool_calls: int = MAX_TOOL_CALLS
    max_execution_time_seconds: float = MAX_EXECUTION_TIME_SECONDS
    max_context_messages: int = MAX_CONTEXT_MESSAGES
    max_web_content_length: int = MAX_WEB_CONTENT_LENGTH
    log_level: str = DEFAULT_LOG_LEVEL
    approval_mode: str = DEFAULT_APPROVAL_MODE   # "always" | "never" | "auto"
    plan_mode: bool = False
    verification_command: str = DEFAULT_VERIFICATION_COMMAND   # empty = disabled
    verification_timeout_seconds: int = DEFAULT_VERIFICATION_TIMEOUT_SECONDS
    firecrawl_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("AGENT_FIRECRAWL_API_KEY", "FIRECRAWL_API_KEY"),
        repr=False,
    )
    rlm_enabled: bool = DEFAULT_RLM_ENABLED
