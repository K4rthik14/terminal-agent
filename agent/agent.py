"""Main agent loop orchestrator.

Responsibilities:
- Owns the primary run() loop for a single agent session.
- Receives user input, forwards to LLMClient, dispatches tool calls via Executor.
- Loops until the LLM produces a final response with no pending tool calls.
- Has no knowledge of rendering, transport, or provider-specific details.
"""

import json
import time

from agent.approver import Approver
from agent.context import AgentContext
from agent.executor import Executor
from cli.renderer import Renderer
from config.defaults import LLM_RETRY_BACKOFF_SECONDS, MAX_LLM_RETRIES
from config.settings import Settings
from context.loop import LoopDetector
from context.metrics import AgentRunMetrics
from context.window import MessageWindow
from llm.base import LLMClient
from tools.registry import ToolRegistry
from utils.errors import LLMError
from utils.logging import get_logger
from utils.types import ApprovalMode, ToolCall
from verification.verifier import Verifier

logger = get_logger(__name__)

_TRANSIENT_LLM_MARKERS = (
    "connection reset",
    "connection aborted",
    "connection refused",
    "connection error",
    "record_layer_failure",
    "sslerror",
    "timeout",
    "temporarily unavailable",
)


def _is_transient_llm_error(error: LLMError) -> bool:
    """Identify transport failures that are safe to retry."""
    message = str(error).lower()
    return any(marker in message for marker in _TRANSIENT_LLM_MARKERS)


class Agent:
    def __init__(
        self,
        llm: LLMClient,
        registry: ToolRegistry,
        settings: Settings,
        renderer: Renderer | None = None,
        verifier: Verifier | None = None,
        verification_command: str = "",
    ) -> None:
        self._llm = llm
        self._registry = registry
        self._settings = settings
        self._renderer = renderer or Renderer()
        self._verifier = verifier
        self._verification_command = verification_command
        self.last_run_metrics = AgentRunMetrics()

    def run(self, prompt: str, context: AgentContext | None = None) -> str:
        """
        Run a single user prompt to completion. Returns the final text reply.
        If context is None, a fresh context is created (used by sub-agents and single-shot mode).
        If context is provided, the prompt is appended and the session continues.
        """
        if context is None:
            context = AgentContext(
                plan_mode=self._settings.plan_mode,
                max_context_messages=self._settings.max_context_messages,
            )
            context.init_system_message()

        context.add_user_message(prompt)

        approver = Approver(ApprovalMode(self._settings.approval_mode))
        executor = Executor(self._registry, approver, plan_mode=context.plan_mode)
        loop_detector = LoopDetector()
        metrics = AgentRunMetrics()
        self.last_run_metrics = metrics
        started_at = time.monotonic()
        reply = ""

        def budget_reason() -> str | None:
            if (
                getattr(self._settings, "max_execution_time_seconds", 0.0) > 0
                and time.monotonic() - started_at
                >= getattr(self._settings, "max_execution_time_seconds", 0.0)
            ):
                return "max_execution_time"
            if metrics.tool_calls >= getattr(self._settings, "max_tool_calls", 2**31):
                return "max_tool_calls"
            return None

        for _ in range(self._settings.max_iterations):
            reason = budget_reason()
            if reason is not None:
                metrics.mark_budget_exceeded(reason)
                break
            self._renderer.thinking()
            # Accumulate streaming response
            reply = ""
            tool_calls: list[ToolCall] = []
            finish_reason = None

            selection = context.select_context(self._registry.all())
            metrics.record_context(
                message_count=len(selection.messages),
                character_count=MessageWindow.estimate_characters(selection.messages),
                tool_count=len(selection.tool_schemas),
            )

            retry_count = 0
            while True:
                try:
                    for event in self._llm.stream(selection.messages, selection.tool_schemas):
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
                    break
                except LLMError as e:
                    if retry_count >= MAX_LLM_RETRIES or not _is_transient_llm_error(e):
                        print(f"\nLLM error: {e}")
                        metrics.finish(False)
                        return f"Error: {e}"
                    retry_count += 1
                    self._renderer.info(
                        f"Retrying LLM request ({retry_count}/{MAX_LLM_RETRIES})..."
                    )
                    time.sleep(LLM_RETRY_BACKOFF_SECONDS)

            print()  # newline after streaming

            reason = budget_reason()
            if reason is not None:
                metrics.mark_budget_exceeded(reason)
                break

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
                    reason = budget_reason()
                    if reason is not None:
                        metrics.mark_budget_exceeded(reason)
                        break
                    try:
                        args = json.loads(tc.arguments or "{}")
                    except json.JSONDecodeError:
                        args = {}
                    started_at = self._renderer.executing(tc.name, args)
                    metrics.record_tool(tc.name)
                    if loop_detector.observe(tc.name, args):
                        result_content = (
                            "Repeated tool call blocked to prevent an execution loop. "
                            "Try a different action or inspect the previous result."
                        )
                        self._renderer.completed_tool(tc.name, False, started_at)
                        metrics.loop_detection_events += 1
                        context.add_tool_result(tc.id, result_content)
                        continue
                    result = executor.run(tc)
                    self._renderer.completed_tool(tc.name, not result.is_error, started_at)
                    context.add_tool_result(result.tool_call_id, result.content)
            else:
                # A configured verifier turns a candidate final reply into a
                # deterministic check-and-repair turn. No command means the
                # historical behavior: finish immediately.
                if self._verifier is not None and self._verification_command.strip():
                    verification = self._verifier.verify_test(self._verification_command)
                    metrics.record_verification(
                        verification.passed,
                        error=verification.error is not None or verification.timed_out,
                    )
                    if not verification.passed:
                        detail = verification.error or verification.output or "verification failed"
                        detail = " ".join(detail.split())[:2000]
                        context.add_assistant_message(content=reply)
                        context.add_tool_result(
                            "verification",
                            f"Verification failed for the configured check: {detail}. "
                            "Repair the task and try again.",
                        )
                        continue
                # Final reply — no more tool calls
                context.add_assistant_message(content=reply)
                self._renderer.completed()
                metrics.finish(True)
                return reply

        if (
            not metrics.budget_exceeded
            and self._settings.max_iterations <= len(metrics.context_message_counts)
        ):
            metrics.mark_budget_exceeded("max_iterations")
        self._renderer.completed()
        metrics.finish(False)
        return reply
