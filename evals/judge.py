"""Execute task verification commands using the existing Verifier."""

from __future__ import annotations

from verification.verifier import Verifier


def check(command: str, timeout_seconds: int = 30) -> tuple[bool, str]:
    """Run a task's verification command; return (passed, detail).

    The command runs in the process's current working directory, so the
    runner chdirs into the isolated workspace before judging.
    """
    result = Verifier(timeout_seconds=timeout_seconds).verify_test(command)
    detail = result.error or result.output or ""
    return result.passed, detail
