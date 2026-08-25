"""Regression coverage for the demo's failed write and provider-error sequence."""

from types import SimpleNamespace

from agent.agent import Agent
from agent.approver import Approver
from agent.executor import Executor
from tools.file_write import WriteFileTool
from tools.registry import ToolRegistry
from utils.errors import LLMError
from utils.types import ApprovalMode, StreamEvent, ToolCall


class QuietRenderer:
    def thinking(self) -> None:
        pass

    def executing(self, name: str, args: dict) -> float:
        return 0.0

    def completed_tool(self, name: str, success: bool, started_at: float) -> None:
        pass

    def completed(self) -> None:
        pass

    def info(self, message: str) -> None:
        pass


class DemoFailureLLM:
    """Fail on the request after the write result, like the demo run."""

    def __init__(self) -> None:
        self.requests: list[tuple[list[dict], list[dict]]] = []

    def stream(self, messages, tool_schemas):
        self.requests.append((messages, tool_schemas))
        if len(self.requests) == 1:
            return iter(
                [
                    StreamEvent(
                        type="tool_call_delta",
                        tool_call_index=0,
                        tool_call_id="write-1",
                        tool_call_name="write_file",
                        content='{"path":"demo/site/index.html","content":"page"}',
                    ),
                    StreamEvent(type="done", finish_reason="tool_calls"),
                ]
            )
        raise LLMError("OpenAI API request failed: [SSL: RECORD_LAYER_FAILURE] record layer failure")


def _settings() -> SimpleNamespace:
    return SimpleNamespace(
        plan_mode=False,
        max_context_messages=24,
        approval_mode="never",
        max_iterations=5,
        max_tool_calls=100,
        max_execution_time_seconds=0.0,
    )


def test_write_file_creates_missing_parent_directories(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    registry = ToolRegistry()
    registry.register(WriteFileTool())
    executor = Executor(registry, Approver(ApprovalMode.NEVER))

    result = executor.run(
        ToolCall(
            id="write-1",
            name="write_file",
            arguments='{"path":"demo/site/index.html","content":"page"}',
        )
    )

    assert result.is_error is False
    assert (tmp_path / "demo" / "site" / "index.html").read_text() == "page"


def test_demo_write_and_independent_ssl_failure_are_handled_safely(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    registry = ToolRegistry()
    registry.register(WriteFileTool())
    llm = DemoFailureLLM()
    agent = Agent(llm, registry, _settings(), renderer=QuietRenderer())

    reply = agent.run("Build a landing page in demo")

    assert "RECORD_LAYER_FAILURE" in reply
    assert len(llm.requests) == 4
    second_messages = llm.requests[1][0]
    tool_result = next(message for message in second_messages if message.get("role") == "tool")
    assert tool_result["tool_call_id"] == "write-1"
    assert "Wrote demo/site/index.html" in tool_result["content"]
    assert "Retrying" not in reply
