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

    def select(self, state: ContextState) -> list[str]:
        """Return lightweight file references relevant to the stored goal.

        This method only parses path-like references and carries forward active
        file hints. It never opens, stats, or otherwise loads file contents.
        """
        selected: list[str] = []
        for raw_path in (*state.active_files, *_PATH_PATTERN.findall(state.goal)):
            path = Path(raw_path)
            reference = str(path)
            if reference not in selected:
                selected.append(reference)
            if len(selected) >= self._max_files:
                break
        return selected[: self._max_files]
