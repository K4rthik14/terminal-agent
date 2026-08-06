"""Builds the stable system context for an agent session."""

from __future__ import annotations

import os
from pathlib import Path

from config.defaults import AGENT_INSTRUCTIONS_FILE


class ContextBuilder:
    """Composes base prompt, environment facts, and project instructions."""

    def __init__(
        self,
        prompt_file: Path | None = None,
        instructions_file: str = AGENT_INSTRUCTIONS_FILE,
    ) -> None:
        self._prompt_file = prompt_file or Path(__file__).parent / "prompts" / "system.md"
        self._instructions_file = Path(instructions_file)

    def build_system_prompt(self) -> str:
        """Return the current system prompt without conversation history."""
        sections = [self._read_prompt(), self._environment_section()]
        instructions = self._read_instructions()
        if instructions:
            sections.append(f"Project instructions:\n{instructions}")
        return "\n\n".join(section for section in sections if section)

    def _read_prompt(self) -> str:
        try:
            return self._prompt_file.read_text(encoding="utf-8").strip()
        except OSError:
            return "You are nanocode, a terminal coding agent. Be concise and action-oriented."

    def _environment_section(self) -> str:
        try:
            entries = sorted(os.listdir("."))
        except OSError:
            entries = []
        files = ", ".join(entries)
        return f"Environment:\ncwd: {os.getcwd()}\nos: {os.uname().sysname}\nfiles in cwd: {files}"

    def _read_instructions(self) -> str:
        try:
            return self._instructions_file.read_text(encoding="utf-8").strip()
        except OSError:
            return ""
