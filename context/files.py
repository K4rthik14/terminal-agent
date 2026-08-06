"""Relevant file hint selection."""

from __future__ import annotations

import re
from pathlib import Path

from context.models import AgentState

_PATH_PATTERN = re.compile(r"(?:^|\s)([\w./-]+\.[A-Za-z0-9]+)(?:$|\s|[),:])")


class RelevantFileSelector:
    """Selects explicit file references from the active request and recent state."""

    def __init__(self, workspace: Path | None = None, max_files: int = 12) -> None:
        self._workspace = workspace or Path.cwd()
        self._max_files = max_files

    def select(self, goal: str, state: AgentState) -> list[str]:
        """Return unique relative file hints, preferring files named by the user."""
        text = "\n".join(
            [goal]
            + [str(message.get("content", "")) for message in state.messages[-6:]]
        )
        selected: list[str] = []
        for raw_path in _PATH_PATTERN.findall(text):
            path = Path(raw_path)
            try:
                relative = str(path if path.is_absolute() else path)
                if relative not in selected:
                    selected.append(relative)
            except (OSError, ValueError):
                continue
            if len(selected) >= self._max_files:
                break
        return selected
