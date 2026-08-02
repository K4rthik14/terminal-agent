"""Pydantic settings model.

Responsibilities:
- Defines the Settings class using pydantic-settings BaseSettings.
- Reads configuration from environment variables and .env file.
- Fields include: model, provider, api_key, max_tokens, approval_mode, log_level.
- Single source of truth for all user-configurable values.
- CLI flag overrides are applied here after initial load.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from config.defaults import (
    DEFAULT_MODEL,
    DEFAULT_BASE_URL,
    DEFAULT_PROVIDER,
    DEFAULT_LOG_LEVEL,
    DEFAULT_APPROVAL_MODE,
    MAX_ITERATIONS,
    MAX_WEB_CONTENT_LENGTH,
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AGENT_", env_file=".env", extra="ignore")

    provider: str = DEFAULT_PROVIDER
    base_url: str = DEFAULT_BASE_URL
    model: str = DEFAULT_MODEL
    api_key: str = ""           # AGENT_API_KEY — falls back to OPENROUTER_API_KEY in main.py
    max_tokens: int = 4096
    max_iterations: int = MAX_ITERATIONS
    max_web_content_length: int = MAX_WEB_CONTENT_LENGTH
    log_level: str = DEFAULT_LOG_LEVEL
    approval_mode: str = DEFAULT_APPROVAL_MODE   # "always" | "never" | "auto"
    plan_mode: bool = False
    firecrawl_api_key: str = ""  # AGENT_FIRECRAWL_API_KEY — falls back to FIRECRAWL_API_KEY in main.py
