"""Tests for user-facing CLI error handling.

Covers the distinction between configuration errors and unexpected internal
errors, and ensures configuration messages never echo environment values.
"""

import argparse

import pytest
from pydantic import ValidationError

from cli.main import invalid_config_message, resolve_settings, unexpected_error_message
from config.settings import Settings
from utils.errors import AgentError, ConfigError

_BAD_VALUE = "not-a-number"


def _noop_args() -> argparse.Namespace:
    return argparse.Namespace(model="", plan=False, no_approval=False)


def test_invalid_env_value_raises_config_error(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_MAX_TOKENS", _BAD_VALUE)
    with pytest.raises(ConfigError):
        resolve_settings(_noop_args())


def test_config_error_names_variable_but_not_value(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_MAX_TOKENS", _BAD_VALUE)
    with pytest.raises(ConfigError) as excinfo:
        resolve_settings(_noop_args())
    message = str(excinfo.value)
    assert "AGENT_MAX_TOKENS" in message
    assert _BAD_VALUE not in message


def test_invalid_config_message_from_real_validation_error(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_MAX_TOKENS", _BAD_VALUE)
    with pytest.raises(ValidationError) as excinfo:
        Settings(_env_file=None)
    message = invalid_config_message(excinfo.value)
    assert "Invalid configuration" in message
    assert "AGENT_MAX_TOKENS" in message


def test_unexpected_error_message_includes_type_and_debug_hint() -> None:
    message = unexpected_error_message(ValueError("boom"))
    assert "ValueError" in message
    assert "boom" in message
    assert "AGENT_LOG_LEVEL=debug" in message


def test_config_error_is_an_agent_error() -> None:
    assert issubclass(ConfigError, AgentError)
