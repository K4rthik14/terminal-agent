"""Bounded reflection over a failed agent attempt."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from llm.base import LLMClient
from utils.logging import get_logger

logger = get_logger(__name__)

_MAX_TRAJECTORY_STEPS = 30
_MAX_FIELD_CHARS = 2000


@dataclass(frozen=True)
class TrajectoryStep:
    """One structured tool invocation and its observed result."""

    tool_name: str
    arguments: dict[str, Any]
    result: str
    is_error: bool = False


@dataclass(frozen=True)
class RLMReflection:
    """Actionable reflection to guide one subsequent agent attempt."""

    what_went_wrong: str
    likely_root_cause: str
    next_strategy: str

    def as_prompt(self) -> str:
        return (
            "Reflection on the previous attempt:\n"
            f"- What went wrong: {self.what_went_wrong}\n"
            f"- Likely root cause: {self.likely_root_cause}\n"
            f"- Change for the next attempt: {self.next_strategy}"
        )


class RLMReflector:
    """Ask the configured LLM for a bounded, structured failure analysis."""

    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    def reflect(
        self,
        task: str,
        trajectory: list[TrajectoryStep],
        failure: str,
    ) -> RLMReflection | None:
        """Return a reflection, or ``None`` if analysis fails or is malformed."""
        bounded_steps = trajectory[-_MAX_TRAJECTORY_STEPS:]
        serialized_trajectory = [
            {
                "tool": step.tool_name,
                "arguments": _bounded(json.dumps(step.arguments, sort_keys=True)),
                "result": _bounded(step.result),
                "is_error": step.is_error,
            }
            for step in bounded_steps
        ]
        payload = {
            "task": _bounded(task),
            "failure": _bounded(failure),
            "trajectory": serialized_trajectory,
        }
        messages = [
            {
                "role": "system",
                "content": (
                    "Analyze the failed coding-agent attempt using the supplied task, "
                    "execution trajectory, and failure. Return only a JSON object with "
                    "three concise string fields: what_went_wrong, likely_root_cause, "
                    "and next_strategy. The strategy must describe concrete changes "
                    "for the next attempt. Do not claim changes were made."
                ),
            },
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ]
        try:
            response = "".join(
                event.content
                for event in self._llm.stream(messages, [])
                if event.type == "token"
            )
            data = json.loads(_strip_json_fence(response))
            if not isinstance(data, dict):
                return None
            what_went_wrong = data.get("what_went_wrong")
            likely_root_cause = data.get("likely_root_cause")
            next_strategy = data.get("next_strategy")
            if (
                not isinstance(what_went_wrong, str)
                or not what_went_wrong.strip()
                or not isinstance(likely_root_cause, str)
                or not likely_root_cause.strip()
                or not isinstance(next_strategy, str)
                or not next_strategy.strip()
            ):
                return None
            return RLMReflection(
                _bounded(what_went_wrong.strip()),
                _bounded(likely_root_cause.strip()),
                _bounded(next_strategy.strip()),
            )
        except Exception:
            logger.exception("RLM reflection failed; continuing without a revised strategy")
            return None


def _bounded(value: str) -> str:
    if len(value) <= _MAX_FIELD_CHARS:
        return value
    return value[:_MAX_FIELD_CHARS] + " [truncated]"


def _strip_json_fence(value: str) -> str:
    text = value.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) >= 3 and lines[-1].strip() == "```":
            return "\n".join(lines[1:-1]).strip()
    return text
