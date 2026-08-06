"""Detection of repetitive tool execution patterns."""

from __future__ import annotations

import json
from collections import deque
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ToolInvocation:
    """Stable representation of one tool invocation."""

    name: str
    arguments: str


class LoopDetector:
    """Blocks only repeated identical tool calls within a bounded window."""

    def __init__(self, max_repeats: int = 2, window_size: int = 8) -> None:
        if max_repeats < 1:
            raise ValueError("max_repeats must be positive")
        if window_size < max_repeats:
            raise ValueError("window_size must be at least max_repeats")
        self._max_repeats = max_repeats
        self._history: deque[ToolInvocation] = deque(maxlen=window_size)

    def observe(self, name: str, arguments: Mapping[str, Any] | str | None = None) -> bool:
        """Record a call and return whether it should be blocked as repetitive."""
        invocation = ToolInvocation(name=name, arguments=self._canonicalize(arguments))
        repeated = sum(item == invocation for item in self._history) >= self._max_repeats - 1
        self._history.append(invocation)
        return repeated

    def reset(self) -> None:
        """Clear observed execution history for a new workflow."""
        self._history.clear()

    @staticmethod
    def _canonicalize(arguments: Mapping[str, Any] | str | None) -> str:
        if arguments is None:
            return "{}"
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments or "{}")
            except json.JSONDecodeError:
                return arguments
        return json.dumps(arguments, sort_keys=True, separators=(",", ":"))
