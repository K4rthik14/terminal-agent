"""Pydantic settings model.

Responsibilities:
- Defines the Settings class using pydantic-settings BaseSettings.
- Reads configuration from environment variables and .env file.
- Fields include: model, provider, api_key, max_tokens, approval_mode, log_level.
- Single source of truth for all user-configurable values.
- CLI flag overrides are applied here after initial load.
"""
