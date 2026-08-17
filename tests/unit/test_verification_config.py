"""Focused tests for CLI wiring of optional deterministic verification."""

from config.defaults import (
    DEFAULT_VERIFICATION_COMMAND,
    DEFAULT_VERIFICATION_TIMEOUT_SECONDS,
)
from config.settings import Settings
from cli.main import build_agent
from tools.registry import ToolRegistry
from verification.verifier import Verifier


def make_settings(monkeypatch, *, command: str | None = None, timeout: int | None = None) -> Settings:
    """Build Settings isolated from .env with the verification env vars controlled."""
    if command is None:
        monkeypatch.delenv("AGENT_VERIFICATION_COMMAND", raising=False)
    else:
        monkeypatch.setenv("AGENT_VERIFICATION_COMMAND", command)
    if timeout is None:
        monkeypatch.delenv("AGENT_VERIFICATION_TIMEOUT_SECONDS", raising=False)
    else:
        monkeypatch.setenv("AGENT_VERIFICATION_TIMEOUT_SECONDS", str(timeout))
    settings = Settings(_env_file=None)
    settings.api_key = "test-key"
    return settings


def test_verification_disabled_by_default(monkeypatch) -> None:
    settings = make_settings(monkeypatch)

    assert settings.verification_command == DEFAULT_VERIFICATION_COMMAND
    assert settings.verification_command == ""
    assert settings.verification_timeout_seconds == DEFAULT_VERIFICATION_TIMEOUT_SECONDS


def test_verification_configuration_loaded_from_env(monkeypatch) -> None:
    settings = make_settings(monkeypatch, command="pytest -q", timeout=45)

    assert settings.verification_command == "pytest -q"
    assert settings.verification_timeout_seconds == 45


def test_build_agent_injects_verifier_when_configured(monkeypatch) -> None:
    settings = make_settings(monkeypatch, command="pytest -q", timeout=45)

    agent = build_agent(settings, ToolRegistry())

    assert isinstance(agent._verifier, Verifier)
    assert agent._verification_command == "pytest -q"


def test_build_agent_skips_verifier_when_command_empty(monkeypatch) -> None:
    settings = make_settings(monkeypatch)

    agent = build_agent(settings, ToolRegistry())

    assert agent._verifier is None
    assert agent._verification_command == ""
