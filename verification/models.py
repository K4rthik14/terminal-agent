"""Contracts for deterministic task verification."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class VerificationResult:
    """Result of one deterministic verification check."""

    passed: bool
    check: str
    command: str
    output: str = ""
    error: str | None = None
    exit_code: int | None = None
    timed_out: bool = False
