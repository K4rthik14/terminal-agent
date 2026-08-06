"""Lightweight task-to-role routing."""

from __future__ import annotations

from orchestration.models import AgentRole, DelegatedTask


class RoleRouter:
    """Routes a prompt to the most appropriate specialized role."""

    _ROLE_KEYWORDS: dict[AgentRole, tuple[str, ...]] = {
        AgentRole.PLANNER: ("plan", "break down", "steps", "approach"),
        AgentRole.REVIEWER: ("review", "audit", "check", "inspect", "verify"),
        AgentRole.RESEARCHER: ("research", "search", "investigate", "documentation"),
    }

    def route(self, prompt: str, task_id: str = "task") -> DelegatedTask:
        """Create a focused task using keyword-based role routing."""
        normalized = prompt.lower()
        role = AgentRole.EXECUTOR
        for candidate, keywords in self._ROLE_KEYWORDS.items():
            if any(keyword in normalized for keyword in keywords):
                role = candidate
                break
        return DelegatedTask(task_id=task_id, prompt=prompt, role=role)
