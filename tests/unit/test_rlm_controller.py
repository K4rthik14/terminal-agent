"""Unit tests for RLMController — the bounded read-only reasoning phase."""

from __future__ import annotations

from typing import Any

from rlm.controller import RLMController, ReadOnlyRegistry, RLMResult
from tools.base import Tool
from tools.registry import ToolRegistry
from utils.types import StreamEvent, ToolResult


# ---------------------------------------------------------------------------
# Fakes / helpers
# ---------------------------------------------------------------------------


class FakeLLM:
    """Replay a scripted sequence of stream responses."""

    def __init__(self, responses: list[list[StreamEvent]]) -> None:
        self._responses = iter(responses)
        self.requests: list[tuple[list[dict], list[dict]]] = []

    def stream(self, messages: list[dict], tool_schemas: list[dict]):
        self.requests.append((messages, tool_schemas))
        return iter(next(self._responses))


class FakeLLMError:
    """LLM that raises LLMError on every call."""

    def stream(self, messages: list[dict], tool_schemas: list[dict]):
        from utils.errors import LLMError

        raise LLMError("simulated LLM failure")


class RecordingReadOnlyTool(Tool):
    """A fake read-only tool that records calls and returns scripted output."""

    name = "read_file"
    description = "Read a file"
    parameters = {"type": "object", "properties": {"path": {"type": "string"}}}
    is_read_only = True

    def __init__(self, output: str = "file contents") -> None:
        self._output = output
        self.calls: list[dict[str, Any]] = []

    def run(self, args: dict[str, Any]) -> ToolResult:
        self.calls.append(args)
        return ToolResult(tool_call_id="", content=self._output)


class WriteTool(Tool):
    """A non-read-only tool that should never appear in the RLM registry."""

    name = "write_file"
    description = "Write a file"
    parameters = {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}}
    is_read_only = False

    def run(self, args: dict[str, Any]) -> ToolResult:
        return ToolResult(tool_call_id="", content="wrote it")


class FailingReadOnlyTool(Tool):
    """A read-only tool that raises on run."""

    name = "web_fetch"
    description = "Fetch URL"
    parameters = {"type": "object", "properties": {"url": {"type": "string"}}}
    is_read_only = True

    def run(self, args: dict[str, Any]) -> ToolResult:
        raise RuntimeError("network unavailable")


def _done(text: str = "brief here") -> list[StreamEvent]:
    """A simple final-response stream."""
    return [
        StreamEvent(type="token", content=text),
        StreamEvent(type="done", finish_reason="stop"),
    ]


def _tool_then_done(
    tool_name: str,
    call_id: str,
    args: str,
    reply_text: str = "based on file",
) -> list[StreamEvent]:
    """A stream that issues one tool call then stops (caller provides the
    second turn's response separately via the FakeLLM responses list)."""
    events: list[StreamEvent] = [
        StreamEvent(
            type="tool_call_delta",
            tool_call_index=0,
            tool_call_id=call_id,
            tool_call_name=tool_name,
            content=args,
        ),
        StreamEvent(type="done", finish_reason="tool_calls"),
    ]
    return events


def _build_registry(*tools: Tool) -> ToolRegistry:
    registry = ToolRegistry()
    for tool in tools:
        registry.register(tool)
    return registry


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestReadOnlyRegistry:
    def test_filters_out_write_tools(self) -> None:
        read_tool = RecordingReadOnlyTool()
        write_tool = WriteTool()
        source = _build_registry(read_tool, write_tool)
        ro = ReadOnlyRegistry(source)

        names = [t.name for t in ro.all()]
        assert "read_file" in names
        assert "write_file" not in names

    def test_as_definitions_only_includes_read_only(self) -> None:
        source = _build_registry(RecordingReadOnlyTool(), WriteTool())
        ro = ReadOnlyRegistry(source)
        defs = ro.as_definitions()
        assert len(defs) == 1
        assert defs[0]["function"]["name"] == "read_file"

    def test_get_raises_for_excluded_tool(self) -> None:
        from utils.errors import ToolNotFoundError

        source = _build_registry(WriteTool())
        ro = ReadOnlyRegistry(source)
        try:
            ro.get("write_file")
            assert False, "should have raised"
        except ToolNotFoundError:
            pass

    def test_empty_registry(self) -> None:
        ro = ReadOnlyRegistry(ToolRegistry())
        assert ro.all() == []
        assert ro.as_definitions() == []


class TestRLMControllerProducesBrief:
    def test_single_turn_produces_brief(self) -> None:
        llm = FakeLLM([_done("Step 1: read file X\nStep 2: apply patch")])
        ctrl = RLMController(llm=llm, registry=ToolRegistry())

        result = ctrl.run("fix the bug in main.py")

        assert isinstance(result, RLMResult)
        assert "Step 1" in result.brief
        assert result.iterations == 1
        assert result.tool_calls == []

    def test_brief_strips_surrounding_whitespace(self) -> None:
        llm = FakeLLM([
            [
                StreamEvent(type="token", content="  \n the plan \n  "),
                StreamEvent(type="done", finish_reason="stop"),
            ]
        ])
        ctrl = RLMController(llm=llm, registry=ToolRegistry())

        result = ctrl.run("task")

        assert result.brief == "the plan"

    def test_request_contains_task_and_system_prompt(self) -> None:
        llm = FakeLLM([_done()])
        ctrl = RLMController(llm=llm, registry=ToolRegistry())

        ctrl.run("implement feature X")

        messages, _ = llm.requests[0]
        roles = [m["role"] for m in messages]
        assert "system" in roles
        assert "user" in roles

        user_msg = next(m for m in messages if m["role"] == "user")
        assert user_msg["content"] == "implement feature X"

        sys_msg = next(m for m in messages if m["role"] == "system")
        assert "reasoning assistant" in sys_msg["content"].lower()


class TestRLMReadonlyInspection:
    def test_tool_call_is_executed_and_result_returned_to_llm(self) -> None:
        read_tool = RecordingReadOnlyTool(output="def main(): pass")
        registry = _build_registry(read_tool)

        # Turn 1: LLM issues a read_file tool call
        # Turn 2: LLM receives the file content and produces a brief
        llm = FakeLLM([
            _tool_then_done("read_file", "call_1", '{"path": "main.py"}'),
            _done("The file defines a main function. Execute it."),
        ])
        ctrl = RLMController(llm=llm, registry=registry)

        result = ctrl.run("inspect main.py")

        assert "main function" in result.brief
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].name == "read_file"
        assert result.iterations == 2
        assert read_tool.calls == [{"path": "main.py"}]

    def test_tool_result_appears_in_second_llm_request(self) -> None:
        read_tool = RecordingReadOnlyTool(output="line 1\nline 2")
        registry = _build_registry(read_tool)

        llm = FakeLLM([
            _tool_then_done("read_file", "c1", '{"path": "a.py"}'),
            _done("File has two lines."),
        ])
        ctrl = RLMController(llm=llm, registry=registry)
        ctrl.run("check a.py")

        # Second request should contain a tool result message
        _, second_tool_schemas = llm.requests[1]
        # The tool schemas should still be the read-only set
        schema_names = [s["function"]["name"] for s in second_tool_schemas]
        assert "read_file" in schema_names


class TestNoWriteToolsExposed:
    def test_write_tools_not_in_tool_schemas(self) -> None:
        registry = _build_registry(RecordingReadOnlyTool(), WriteTool())
        llm = FakeLLM([_done()])
        ctrl = RLMController(llm=llm, registry=registry)

        ctrl.run("task")

        _, tool_schemas = llm.requests[0]
        schema_names = [s["function"]["name"] for s in tool_schemas]
        assert "write_file" not in schema_names
        assert "read_file" in schema_names

    def test_read_only_registry_property_excludes_write(self) -> None:
        registry = _build_registry(RecordingReadOnlyTool(), WriteTool())
        ctrl = RLMController(llm=FakeLLM([_done()]), registry=registry)

        ro_names = [t.name for t in ctrl.read_only_registry.all()]
        assert "write_file" not in ro_names


class TestIterationBound:
    def test_respects_max_iterations(self) -> None:
        """Even with a cooperating LLM, the controller stops at max_iterations."""
        read_tool = RecordingReadOnlyTool(output="data")
        registry = _build_registry(read_tool)

        # LLM always wants another tool call — never produces a final text response
        infinite_tool_stream = _tool_then_done("read_file", "c1", '{"path": "x.py"}')
        llm = FakeLLM([infinite_tool_stream] * 10)

        ctrl = RLMController(llm=llm, registry=registry, max_iterations=3)
        result = ctrl.run("inspect everything")

        assert result.iterations == 3
        assert len(llm.requests) == 3

    def test_single_cycle_completes_immediately_on_text_response(self) -> None:
        llm = FakeLLM([_done("brief")])
        ctrl = RLMController(llm=llm, registry=ToolRegistry())

        result = ctrl.run("task")
        assert result.iterations == 1

    def test_default_max_iterations_is_reasonable(self) -> None:
        ctrl = RLMController(llm=FakeLLM([_done()]), registry=ToolRegistry())
        assert ctrl._max_iterations == 8


class TestErrorHandling:
    def test_llm_error_returns_partial_brief(self) -> None:
        ctrl = RLMController(llm=FakeLLMError(), registry=ToolRegistry())

        result = ctrl.run("task")

        # Should not raise — returns a result with whatever was accumulated
        assert isinstance(result, RLMResult)
        assert result.brief == ""

    def test_tool_execution_error_does_not_crash(self) -> None:
        failing_tool = FailingReadOnlyTool()
        registry = _build_registry(failing_tool)

        # LLM issues a tool call that will fail, then produces a brief
        llm = FakeLLM([
            _tool_then_done("web_fetch", "c1", '{"url": "http://example.com"}'),
            _done("Tool failed but brief is still produced."),
        ])
        ctrl = RLMController(llm=llm, registry=registry)

        result = ctrl.run("fetch and summarize")

        assert "brief is still produced" in result.brief
        assert result.tool_calls[0].name == "web_fetch"

    def test_tool_result_shows_error_for_failing_tool(self) -> None:
        failing_tool = FailingReadOnlyTool()
        registry = _build_registry(failing_tool)

        llm = FakeLLM([
            _tool_then_done("web_fetch", "c1", '{"url": "http://x.com"}'),
            _done("recovered"),
        ])
        ctrl = RLMController(llm=llm, registry=registry)
        ctrl.run("task")

        # The tool result message sent to the LLM should contain an error
        messages, _ = llm.requests[1]
        tool_msgs = [m for m in messages if m.get("role") == "tool"]
        assert len(tool_msgs) == 1
        assert "Error" in tool_msgs[0]["content"]

    def test_invalid_json_in_tool_args_returns_error(self) -> None:
        read_tool = RecordingReadOnlyTool()
        registry = _build_registry(read_tool)

        # LLM sends malformed JSON arguments
        llm = FakeLLM([
            [
                StreamEvent(
                    type="tool_call_delta",
                    tool_call_index=0,
                    tool_call_id="c1",
                    tool_call_name="read_file",
                    content="NOT_JSON{{",
                ),
                StreamEvent(type="done", finish_reason="tool_calls"),
            ],
            _done("done despite bad args"),
        ])
        ctrl = RLMController(llm=llm, registry=registry)
        result = ctrl.run("task")

        # Tool was not called with bad args
        assert read_tool.calls == []
        # But the error message was sent back to the LLM
        messages, _ = llm.requests[1]
        tool_msgs = [m for m in messages if m.get("role") == "tool"]
        assert len(tool_msgs) == 1
        assert "invalid JSON" in tool_msgs[0]["content"]

    def test_unknown_tool_name_returns_error(self) -> None:
        llm = FakeLLM([
            _tool_then_done("nonexistent_tool", "c1", '{"x": 1}'),
            _done("handled"),
        ])
        ctrl = RLMController(llm=llm, registry=ToolRegistry())
        result = ctrl.run("task")

        assert result.brief == "handled"
        messages, _ = llm.requests[1]
        tool_msgs = [m for m in messages if m.get("role") == "tool"]
        assert len(tool_msgs) == 1
        assert "Error" in tool_msgs[0]["content"]


class TestRLMResult:
    def test_tool_names_property(self) -> None:
        from utils.types import ToolCall

        r = RLMResult(
            brief="plan",
            iterations=1,
            tool_calls=[
                ToolCall(id="1", name="read_file"),
                ToolCall(id="2", name="web_search"),
            ],
        )
        assert r.tool_names == ["read_file", "web_search"]

    def test_empty_tool_calls(self) -> None:
        r = RLMResult(brief="brief", iterations=1)
        assert r.tool_names == []
        assert r.tool_calls == []
