"""Deterministic verification for coding-agent tasks."""

from __future__ import annotations

import subprocess
from collections.abc import Callable

from verification.models import VerificationResult


CommandRunner = Callable[[str, int], subprocess.CompletedProcess[str]]


class Verifier:
    """Runs simple deterministic command or test checks without an LLM."""

    def __init__(
        self,
        timeout_seconds: int = 30,
        command_runner: CommandRunner | None = None,
    ) -> None:
        if timeout_seconds < 1:
            raise ValueError("timeout_seconds must be positive")
        self._timeout_seconds = timeout_seconds
        self._command_runner = command_runner or self._run_command

    def verify_command(self, command: str) -> VerificationResult:
        """Run a command and pass only when it exits with code zero."""
        if not command.strip():
            return VerificationResult(
                passed=False,
                check="command",
                command=command,
                error="Verification command cannot be empty.",
            )

        try:
            completed = self._command_runner(command, self._timeout_seconds)
        except subprocess.TimeoutExpired as exc:
            output = self._timeout_output(exc)
            return VerificationResult(
                passed=False,
                check="command",
                command=command,
                output=output,
                error=f"Command timed out after {self._timeout_seconds} seconds.",
                timed_out=True,
            )
        except OSError as exc:
            return VerificationResult(
                passed=False,
                check="command",
                command=command,
                error=str(exc),
            )

        output = self._combined_output(completed)
        passed = completed.returncode == 0
        return VerificationResult(
            passed=passed,
            check="command",
            command=command,
            output=output,
            error=None if passed else f"Command exited with code {completed.returncode}.",
            exit_code=completed.returncode,
        )

    def verify_test(self, command: str) -> VerificationResult:
        """Verify a test command using the same deterministic command check."""
        result = self.verify_command(command)
        return VerificationResult(
            passed=result.passed,
            check="test",
            command=result.command,
            output=result.output,
            error=result.error,
            exit_code=result.exit_code,
            timed_out=result.timed_out,
        )

    def _run_command(self, command: str, timeout_seconds: int) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )

    @staticmethod
    def _combined_output(result: subprocess.CompletedProcess[str]) -> str:
        return "\n".join(part for part in (result.stdout, result.stderr) if part)

    @staticmethod
    def _timeout_output(exc: subprocess.TimeoutExpired) -> str:
        parts = [part for part in (exc.stdout, exc.stderr) if part]
        return "\n".join(part.decode() if isinstance(part, bytes) else part for part in parts)
