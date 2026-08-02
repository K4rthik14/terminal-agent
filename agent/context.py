"""Agent session context — the single source of mutable session state.

Responsibilities:
- Carries all state for one agent session: message history, tool results,
  active plan, token usage, and metadata.
- Passed by reference through the agent turn. Never stored globally.
- Not persisted in Phase 1; designed to be serializable for Phase 2 memory support.
"""

import os
from dataclasses import dataclass, field
from typing import Any
from utils.types import MessageList


@dataclass
class AgentContext:
    """All mutable state for one agent session."""

    messages: MessageList = field(default_factory=list)
    plan_mode: bool = False
    auto_approve: bool = False

    def add_user_message(self, content: str) -> None:
        self.messages.append({"role": "user", "content": content})

    def add_assistant_message(self, content: str, tool_calls: list[dict[str, Any]] | None = None) -> None:
        msg: dict[str, Any] = {"role": "assistant", "content": content}
        if tool_calls:
            msg["tool_calls"] = tool_calls
        self.messages.append(msg)

    def add_tool_result(self, tool_call_id: str, content: str) -> None:
        self.messages.append({"role": "tool", "tool_call_id": tool_call_id, "content": content})

    def system_prompt(self) -> str:
        cwd = os.getcwd()
        try:
            files = ", ".join(sorted(os.listdir(".")))
        except OSError:
            files = ""
        prompt = (
            "You are nanocode, a terminal coding agent. Be concise. Prefer tools over guessing.\n"
            "Use the todo_write tool to plan any task with more than a couple of steps.\n\n"
            f"Environment:\ncwd: {cwd}\nos: {os.uname().sysname}\n"
            f"files in cwd: {files}"
        )
        instructions_file = "NANOCODE.md"
        if os.path.exists(instructions_file):
            try:
                with open(instructions_file, encoding="utf-8") as f:
                    prompt += f"\n\nProject instructions:\n{f.read()}"
            except OSError:
                pass
        return prompt

    def init_system_message(self) -> None:
        """Prepend system message. Call once at session start."""
        self.messages.insert(0, {"role": "system", "content": self.system_prompt()})
