"""RLM controller — bounded read-only reasoning before execution.

Responsibilities:
- Accepts an existing LLMClient, ToolRegistry, and Settings via DI.
- Filters the registry to read-only tools only.
- Performs exactly one LLM reasoning cycle: the model may call read-only
  tools to inspect files, then must produce a concise execution brief.
- Returns an RLMResult dataclass with the brief, iteration count, and
  any tool calls made during the reasoning phase.
- Never writes files, never modifies state, never recurses.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from context.builder import ContextBuilder
from llm.base import LLMClient
from tools.base import Tool
from tools.registry import ToolRegistry
from utils.errors import LLMError
from utils.logging import get_logger
from utils.types import StreamEvent, ToolCall, ToolResult

logger = get_logger(__name__)

_RLM_SYSTEM_PROMPT = (
    "You are a reasoning assistant preparing an execution brief.\n"
    "Your job: understand the task, inspect relevant files using the "
    "read-only tools available to you, identify constraints and dependencies,\n"
    "then produce a concise execution brief that the main agent can act on.\n\n"
    "Rules:\n"
    "- You may only use read-only tools (read_file, web_search, web_fetch, todo_write).\n"
    "- Do NOT write, edit, or delete any files.\n"
    "- Keep your brief focused: state what needs to be done, in what order,\n"
    "  what constraints apply, and any important file paths or dependencies.\n"
    "- End your response with the execution brief clearly separated.\n"
)


class ReadOnlyRegistry(ToolRegistry):
    """Wraps a ToolRegistry, exposing only read-only tools.

    Inherits all public methods from ToolRegistry. Tools with
    ``is_read_only=False`` are excluded from every query.
    """

    def __init__(self, source: ToolRegistry) -> None:
        # Initialise empty parent
        super().__init__()
        for tool in source.all():
            if tool.is_read_only:
                # Parent.register raises on duplicates; read-only set is unique
                super().register(tool)


@dataclass(frozen=True)
class RLMResult:
    """Structured output from one RLM reasoning phase."""

    brief: str
    iterations: int
    tool_calls: list[ToolCall] = field(default_factory=list)

    @property
    def tool_names(self) -> list[str]:
        return [tc.name for tc in self.tool_calls]


class RLMController:
    """Performs exactly one bounded, read-only reasoning cycle.

    Accepts all dependencies through construction (no global state).
    """

    def __init__(
        self,
        llm: LLMClient,
        registry: ToolRegistry,
        *,
        system_prompt: str | None = None,
        max_iterations: int = 8,
    ) -> None:
        self._llm = llm
        self._read_only_registry = ReadOnlyRegistry(registry)
        self._system_prompt = system_prompt or _RLM_SYSTEM_PROMPT
        self._max_iterations = max_iterations
        self._context_builder = ContextBuilder()

    @property
    def read_only_registry(self) -> ReadOnlyRegistry:
        """Expose the filtered registry for inspection / testing."""
        return self._read_only_registry

    def run(self, task: str) -> RLMResult:
        """Execute one bounded reasoning cycle for the given task.

        The model receives the task plus a system prompt instructing it to
        produce an execution brief.  It may call read-only tools during its
        reasoning, but at most ``_max_iterations`` tool-turns are allowed.

        Returns:
            RLMResult with the final brief, iteration count, and tool calls.
        """
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": self._build_system_message()},
            {"role": "user", "content": task},
        ]
        tool_schemas = self._read_only_registry.as_definitions()
        all_tool_calls: list[ToolCall] = []

        for iteration in range(self._max_iterations):
            reply, tool_calls, finish_reason = self._stream_one_turn(
                messages, tool_schemas
            )
            all_tool_calls.extend(tool_calls)

            if finish_reason != "tool_calls" or not tool_calls:
                # Model produced a final text response — done.
                return RLMResult(
                    brief=reply.strip(),
                    iterations=iteration + 1,
                    tool_calls=all_tool_calls,
                )

            # Append assistant message with tool calls to conversation
            messages.append(
                {
                    "role": "assistant",
                    "content": reply,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.name,
                                "arguments": tc.arguments,
                            },
                        }
                        for tc in tool_calls
                    ],
                }
            )

            # Execute each read-only tool call and append results
            for tc in tool_calls:
                result = self._execute_read_only(tc)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": result.tool_call_id,
                        "content": result.content,
                    }
                )

        # Exhausted iterations — return whatever brief we have
        logger.warning("RLM phase exhausted %d iterations", self._max_iterations)
        # The last reply was captured during streaming; reconstruct from messages
        last_assistant = next(
            (m for m in reversed(messages) if m.get("role") == "assistant"),
            {"content": ""},
        )
        return RLMResult(
            brief=str(last_assistant.get("content", "")).strip(),
            iterations=self._max_iterations,
            tool_calls=all_tool_calls,
        )

    # -- internal helpers ---------------------------------------------------

    def _build_system_message(self) -> str:
        """Combine the RLM prompt with the environment context."""
        env_section = self._context_builder._environment_section()
        return f"{self._system_prompt}\n\n{env_section}"

    def _stream_one_turn(
        self,
        messages: list[dict[str, Any]],
        tool_schemas: list[dict[str, Any]],
    ) -> tuple[str, list[ToolCall], str | None]:
        """Stream one LLM turn, accumulating reply text and tool calls.

        Returns (reply_text, tool_calls, finish_reason).
        """
        reply = ""
        tool_calls: list[ToolCall] = []
        finish_reason: str | None = None

        try:
            for event in self._llm.stream(messages, tool_schemas):
                if event.type == "token":
                    reply += event.content
                elif event.type == "tool_call_delta":
                    idx = event.tool_call_index
                    while len(tool_calls) <= idx:
                        tool_calls.append(ToolCall(id="", name=""))
                    tc = tool_calls[idx]
                    tc.id += event.tool_call_id
                    tc.name += event.tool_call_name
                    tc.arguments += event.content
                elif event.type == "done":
                    finish_reason = event.finish_reason
        except LLMError as exc:
            logger.error("LLM error during RLM phase: %s", exc)
            # Treat as a terminal state — return what we have
            return reply, tool_calls, None

        return reply, tool_calls, finish_reason

    def _execute_read_only(self, tool_call: ToolCall) -> ToolResult:
        """Execute a single read-only tool call.  Never raises."""
        try:
            args = json.loads(tool_call.arguments or "{}")
        except json.JSONDecodeError:
            return ToolResult(
                tool_call_id=tool_call.id,
                content=f"Error: invalid JSON arguments for {tool_call.name}",
                is_error=True,
            )

        try:
            tool = self._read_only_registry.get(tool_call.name)
        except Exception as exc:
            return ToolResult(
                tool_call_id=tool_call.id,
                content=f"Error: {exc}",
                is_error=True,
            )

        # Double-check: never allow non-read-only tools through
        if not tool.is_read_only:
            return ToolResult(
                tool_call_id=tool_call.id,
                content="Error: write tools are not allowed during RLM reasoning.",
                is_error=True,
            )

        try:
            result = tool.run(args)
            result.tool_call_id = tool_call.id
            return result
        except Exception as exc:
            logger.exception("Error executing read-only tool %s", tool_call.name)
            return ToolResult(
                tool_call_id=tool_call.id,
                content=f"Error: {exc}",
                is_error=True,
            )
