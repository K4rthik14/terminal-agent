"""Tests for API-key configuration and missing-key guidance.

Ensures the accepted environment variables resolve correctly and that the
user-facing error names them without ever exposing secret values.
"""

from cli.main import missing_api_key_message
from config.settings import API_KEY_ENV_VARS, Settings

_SECRET = "test-secret-value"


def _settings(monkeypatch, **env: str) -> Settings:
    """Build Settings with a clean environment (no .env file)."""
    for name in API_KEY_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    return Settings(_env_file=None)


def test_primary_api_key_env_var_is_used(monkeypatch) -> None:
    primary, _ = API_KEY_ENV_VARS
    settings = _settings(monkeypatch, **{primary: _SECRET})
    assert settings.api_key == _SECRET


def test_fallback_api_key_env_var_is_used(monkeypatch) -> None:
    _, fallback = API_KEY_ENV_VARS
    settings = _settings(monkeypatch, **{fallback: _SECRET})
    assert settings.api_key == _SECRET


def test_missing_key_message_names_env_vars_only() -> None:
    message = missing_api_key_message()
    for name in API_KEY_ENV_VARS:
        assert name in message


def test_missing_key_message_never_contains_secret_values() -> None:
    message = missing_api_key_message()
    assert _SECRET not in message
    assert "<your-api-key>" in message  # placeholder only, never a real value
