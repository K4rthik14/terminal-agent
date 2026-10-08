"""Composition-root tests for optional single-shot RLM integration."""

from types import SimpleNamespace

from cli.main import build_agent, build_effective_prompt
from config.settings import Settings
from rlm.reflection import RLMReflector
from tools.registry import ToolRegistry


class RecordingRLM:
    def __init__(self, brief: str) -> None:
        self.brief = brief
        self.calls: list[str] = []

    def run(self, prompt: str) -> SimpleNamespace:
        self.calls.append(prompt)
        return SimpleNamespace(brief=self.brief)


def test_rlm_is_disabled_by_default(monkeypatch) -> None:
    monkeypatch.delenv("AGENT_RLM_ENABLED", raising=False)

    assert Settings().rlm_enabled is False


def test_rlm_enabled_loads_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_RLM_ENABLED", "true")

    assert Settings().rlm_enabled is True


def test_build_agent_injects_reflector_only_when_enabled() -> None:
    enabled = Settings(_env_file=None, rlm_enabled=True)
    disabled = Settings(_env_file=None, rlm_enabled=False)

    enabled_agent = build_agent(enabled, ToolRegistry(), llm=object())  # type: ignore[arg-type]
    disabled_agent = build_agent(disabled, ToolRegistry(), llm=object())  # type: ignore[arg-type]

    assert isinstance(enabled_agent._rlm_reflector, RLMReflector)
    assert disabled_agent._rlm_reflector is None


def test_rlm_disabled_preserves_prompt_and_does_not_run() -> None:
    controller = RecordingRLM("unused brief")

    assert build_effective_prompt("fix the bug") == "fix the bug"
    assert controller.calls == []


def test_rlm_enabled_adds_brief_and_preserves_original_task() -> None:
    controller = RecordingRLM("Inspect the failing test before editing.")

    effective = build_effective_prompt("fix the bug", controller)  # type: ignore[arg-type]

    assert controller.calls == ["fix the bug"]
    assert "Execution brief:\nInspect the failing test before editing." in effective
    assert "Now execute the task: fix the bug" in effective


def test_empty_rlm_brief_preserves_original_task() -> None:
    controller = RecordingRLM("")

    assert build_effective_prompt("create the file", controller) == "create the file"  # type: ignore[arg-type]
    assert controller.calls == ["create the file"]
