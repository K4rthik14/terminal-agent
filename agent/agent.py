"""Main agent loop orchestrator.

Responsibilities:
- Owns the primary run() loop for a single agent session.
- Receives user input, forwards to LLMClient, dispatches tool calls via Executor.
- Loops until the LLM produces a final response with no pending tool calls.
- Has no knowledge of rendering, transport, or provider-specific details.
"""

import json
from utils.types import ToolCall, MessageList, ApprovalMode
from utils.errors import LLMError
from utils.logging import get_logger
from llm.base import LLMClient
from tools.registry import ToolRegistry
from agent.context import AgentContext
from agent.approver import Approver
from agent.executor import Executor
from config.settings import Settings
from cli.renderer import Renderer

logger = get_logger(__name__)


class Agent:
    def __init__(
        self,
        llm: LLMClient,
        registry: ToolRegistry,
        settings: Settings,
        renderer: Renderer | None = None,
    ) -> None:
        self._llm = llm
        self._registry = registry
        self._settings = settings
        self._renderer = renderer or Renderer()

    def run(self, prompt: str, context: AgentContext | None = None) -> str:
        """
        Run a single user prompt to completion. Returns the final text reply.
        If context is None, a fresh context is created (used by sub-agents and single-shot mode).
        If context is provided, the prompt is appended and the session continues.
        """
        if context is None:
            context = AgentContext(plan_mode=self._settings.plan_mode)
            context.init_system_message()

        context.add_user_message(prompt)

        approver = Approver(ApprovalMode(self._settings.approval_mode))
        executor = Executor(self._registry, approver, plan_mode=context.plan_mode)
        tool_schemas = self._registry.as_definitions()

        reply = ""
        for _ in range(self._settings.max_iterations):
            self._renderer.thinking()
            # Accumulate streaming response
            reply = ""
            tool_calls: list[ToolCall] = []
            finish_reason = None

            try:
                for event in self._llm.stream(context.messages, tool_schemas):
                    if event.type == "token":
                        print(event.content, end="", flush=True)
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
            except LLMError as e:
                print(f"\nLLM error: {e}")
                return f"Error: {e}"

            print()  # newline after streaming

            if finish_reason == "tool_calls" and tool_calls:
                # Add assistant message with tool calls to context
                context.add_assistant_message(
                    content=reply,
                    tool_calls=[
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {"name": tc.name, "arguments": tc.arguments},
                        }
                        for tc in tool_calls
                    ],
                )
                # Execute all tool calls and append results
                for tc in tool_calls:
                    try:
                        args = json.loads(tc.arguments or "{}")
                    except json.JSONDecodeError:
                        args = {}
                    started_at = self._renderer.executing(tc.name, args)
                    result = executor.run(tc)
                    self._renderer.completed_tool(tc.name, not result.is_error, started_at)
                    context.add_tool_result(result.tool_call_id, result.content)
            else:
                # Final reply — no more tool calls
                context.add_assistant_message(content=reply)
                self._renderer.completed()
                return reply

        self._renderer.completed()
        return reply
