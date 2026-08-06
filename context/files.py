"""Relevant file hint selection."""

from __future__ import annotations

import re
from pathlib import Path

from context.models import ContextState

_PATH_PATTERN = re.compile(r"(?:^|\s)([\w./-]+\.[A-Za-z0-9]+)(?:$|\s|[),:])")


class RelevantFileSelector:
    """Selects file hints from the active goal and compact state."""

    def __init__(self, workspace: Path | None = None, max_files: int = 12) -> None:
        self._workspace = workspace or Path.cwd()
        self._max_files = max_files

    def select(self, goal: str, state: ContextState) -> list[str]:
        """Return unique file hints, preferring active files and explicit paths."""
        selected: list[str] = list(state.active_files[: self._max_files])
        text = "\n".join(
            [goal]
            + [str(message.get("content", "")) for message in state.conversation_tail]
        )
        for raw_path in _PATH_PATTERN.findall(text):
            path = Path(raw_path)
            relative = str(path)
            if relative not in selected:
                selected.append(relative)
            if len(selected) >= self._max_files:
                break
        return selected
