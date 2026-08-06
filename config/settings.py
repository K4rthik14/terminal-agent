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
    DEFAULT_MODEL,
    DEFAULT_BASE_URL,
    DEFAULT_PROVIDER,
    DEFAULT_LOG_LEVEL,
    DEFAULT_APPROVAL_MODE,
    MAX_ITERATIONS,
    MAX_WEB_CONTENT_LENGTH,
    MAX_CONTEXT_MESSAGES,
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AGENT_", env_file=".env", extra="ignore")

    provider: str = DEFAULT_PROVIDER
    base_url: str = DEFAULT_BASE_URL
    model: str = DEFAULT_MODEL
    api_key: str = Field(
        default="",
        validation_alias=AliasChoices("AGENT_API_KEY", "OPENROUTER_API_KEY"),
        repr=False,
    )  # Never store or print API keys; supports both generic and OpenRouter names.
    max_tokens: int = 4096
    max_iterations: int = MAX_ITERATIONS
    max_context_messages: int = MAX_CONTEXT_MESSAGES
    max_web_content_length: int = MAX_WEB_CONTENT_LENGTH
    log_level: str = DEFAULT_LOG_LEVEL
    approval_mode: str = DEFAULT_APPROVAL_MODE   # "always" | "never" | "auto"
    plan_mode: bool = False
    firecrawl_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("AGENT_FIRECRAWL_API_KEY", "FIRECRAWL_API_KEY"),
        repr=False,
    )
