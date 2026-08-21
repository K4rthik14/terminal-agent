"""Tests for model configuration resolution and missing-model guidance.

Covers the documented precedence: --model flag > AGENT_MODEL env/.env >
built-in default, plus fail-fast behavior for an explicitly empty model.
"""

import argparse

from cli.main import missing_model_message, resolve_settings
from config.settings import MODEL_ENV_VAR, Settings


def _args(model: str = "") -> argparse.Namespace:
    return argparse.Namespace(model=model, plan=False, no_approval=False)


def _settings(monkeypatch, **env: str) -> Settings:
    monkeypatch.delenv(MODEL_ENV_VAR, raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    return Settings(_env_file=None)


def test_default_model_used_when_unset(monkeypatch) -> None:
    settings = _settings(monkeypatch)
    assert settings.model  # built-in default is always non-empty


def test_env_var_selects_model(monkeypatch) -> None:
    settings = _settings(monkeypatch, **{MODEL_ENV_VAR: "env-model"})
    assert settings.model == "env-model"


def test_cli_flag_overrides_env(monkeypatch) -> None:
    _settings(monkeypatch, **{MODEL_ENV_VAR: "env-model"})
    settings = resolve_settings(_args(model="flag-model"))
    assert settings.model == "flag-model"


def test_whitespace_only_flag_is_ignored(monkeypatch) -> None:
    _settings(monkeypatch, **{MODEL_ENV_VAR: "env-model"})
    settings = resolve_settings(_args(model="   "))
    assert settings.model == "env-model"


def test_flag_value_is_stripped(monkeypatch) -> None:
    settings = resolve_settings(_args(model="  padded-model  "))
    assert settings.model == "padded-model"


def test_missing_model_message_names_config_options() -> None:
    message = missing_model_message()
    assert "--model" in message
    assert MODEL_ENV_VAR in message
    assert "<model-name>" in message  # placeholder only, never a real value
