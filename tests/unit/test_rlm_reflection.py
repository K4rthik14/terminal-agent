"""Tests for bounded reflection after a failed agent attempt."""

import json

from rlm.reflection import RLMReflector, TrajectoryStep
from utils.types import StreamEvent


class FakeLLM:
    def __init__(self, response: str) -> None:
        self.response = response
        self.requests: list[tuple[list[dict], list[dict]]] = []

    def stream(self, messages, tool_schemas):
        self.requests.append((messages, tool_schemas))
        return iter(
            [
                StreamEvent(type="token", content=self.response),
                StreamEvent(type="done", finish_reason="stop"),
            ]
        )


def test_reflector_returns_structured_strategy_from_trajectory() -> None:
    llm = FakeLLM(
        json.dumps(
            {
                "what_went_wrong": "The test still failed.",
                "likely_root_cause": "The implementation missed an edge case.",
                "next_strategy": "Inspect the failing assertion and handle empty input.",
            }
        )
    )
    trajectory = [
        TrajectoryStep("write_file", {"path": "src.py"}, "wrote src.py"),
        TrajectoryStep("bash", {"command": "pytest -q"}, "1 failed", is_error=True),
    ]

    reflection = RLMReflector(llm).reflect("fix the test", trajectory, "pytest failed")

    assert reflection is not None
    assert reflection.what_went_wrong == "The test still failed."
    assert reflection.likely_root_cause == "The implementation missed an edge case."
    assert "empty input" in reflection.next_strategy
    request_messages, schemas = llm.requests[0]
    assert schemas == []
    payload = json.loads(request_messages[1]["content"])
    assert payload["task"] == "fix the test"
    assert payload["failure"] == "pytest failed"
    assert payload["trajectory"][1]["is_error"] is True


def test_reflector_ignores_malformed_response() -> None:
    reflection = RLMReflector(FakeLLM("not json")).reflect("task", [], "failed")

    assert reflection is None
