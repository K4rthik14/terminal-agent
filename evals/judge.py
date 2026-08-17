"""Execute task verification commands using the existing Verifier."""

from __future__ import annotations

from verification.verifier import Verifier


def check_result(command: str, timeout_seconds: int = 30) -> tuple[bool, str, str | None]:
    """Run verification and return (passed, detail, failure type).

    The command runs in the process's current working directory, so the
    runner chdirs into the isolated workspace before judging.
    """
    result = Verifier(timeout_seconds=timeout_seconds).verify_test(command)
    detail = result.error or result.output or ""
    failure_type = None
    if not result.passed:
        failure_type = "verification_timeout" if result.timed_out else "verification_failed"
    return result.passed, detail, failure_type


def check(command: str, timeout_seconds: int = 30) -> tuple[bool, str]:
    """Run verification and return the legacy (passed, detail) pair."""
    passed, detail, _ = check_result(command, timeout_seconds)
    return passed, detail
