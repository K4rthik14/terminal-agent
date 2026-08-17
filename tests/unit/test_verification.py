"""Unit tests for deterministic verification."""

import subprocess

import pytest

from verification.verifier import Verifier


def test_verify_command_passes_on_zero_exit() -> None:
    result = Verifier().verify_command("printf 'ok'")

    assert result.passed is True
    assert result.check == "command"
    assert result.exit_code == 0
    assert result.output == "ok"
    assert result.error is None


def test_verify_test_reports_test_check() -> None:
    result = Verifier().verify_test("printf 'tests passed'")

    assert result.passed is True
    assert result.check == "test"
    assert result.output == "tests passed"


def test_verify_command_reports_nonzero_exit() -> None:
    result = Verifier().verify_command("sh -c 'printf failed; exit 3'")

    assert result.passed is False
    assert result.exit_code == 3
    assert result.output == "failed"
    assert result.error == "Command exited with code 3."


def test_verify_command_rejects_empty_command() -> None:
    result = Verifier().verify_command("   ")

    assert result.passed is False
    assert result.error == "Verification command cannot be empty."


def test_verify_command_reports_timeout() -> None:
    def timeout_runner(command: str, timeout_seconds: int) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(command, timeout_seconds, output="partial")

    result = Verifier(timeout_seconds=1, command_runner=timeout_runner).verify_command("slow")

    assert result.passed is False
    assert result.timed_out is True
    assert result.error == "Command timed out after 1 seconds."
    assert result.output == "partial"


def test_verify_command_supports_injected_runner() -> None:
    def runner(command: str, timeout_seconds: int) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(command, 0, stdout="injected", stderr="")

    result = Verifier(command_runner=runner).verify_command("ignored")

    assert result.passed is True
    assert result.output == "injected"


def test_verify_command_reports_oserror() -> None:
    def failing_runner(command: str, timeout_seconds: int) -> subprocess.CompletedProcess[str]:
        raise OSError("command not found")

    result = Verifier(command_runner=failing_runner).verify_command("missing-tool")

    assert result.passed is False
    assert result.error == "command not found"


def test_verify_command_timeout_combines_stdout_and_stderr() -> None:
    def timeout_runner(command: str, timeout_seconds: int) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(
            command, timeout_seconds, output=b"partial-out", stderr=b"partial-err"
        )

    result = Verifier(timeout_seconds=1, command_runner=timeout_runner).verify_command("slow")

    assert result.passed is False
    assert result.timed_out is True
    assert result.output == "partial-out\npartial-err"


def test_verifier_rejects_non_positive_timeout() -> None:
    with pytest.raises(ValueError):
        Verifier(timeout_seconds=0)


def test_verify_test_rejects_empty_command() -> None:
    result = Verifier().verify_test("   ")

    assert result.passed is False
    assert result.check == "test"
    assert result.error == "Verification command cannot be empty."
