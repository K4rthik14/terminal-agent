"""CLI entry point.

Responsibilities:
- Parses CLI arguments: --model, --provider, --plan, --no-approval, --prompt, etc.
- Constructs the concrete LLMClient, ToolRegistry, and Settings instances.
- Injects dependencies into the Agent (no global state passed around).
- Starts the REPL if no --prompt is given; otherwise runs a single-shot turn.
"""

import argparse
import os
import sys

from agent.agent import Agent
from agent.context import AgentContext
from cli.renderer import Renderer
from cli.repl import Repl
from config.settings import Settings
from llm.base import LLMClient
from llm.openai_client import OpenAIClient
from rlm.controller import RLMController
from tools.bash import BashTool
from tools.file_edit import EditFileTool
from tools.file_read import ReadFileTool
from tools.file_write import WriteFileTool
from tools.registry import ToolRegistry
from tools.sub_agent import SubAgentTool
from tools.todo import TodoWriteTool
from tools.web_fetch import WebFetchTool
from tools.web_search import WebSearchTool
from utils.logging import configure_logging, get_logger
from verification.verifier import Verifier

logger = get_logger(__name__)


def build_registry(settings: Settings, agent_factory) -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(ReadFileTool())
    registry.register(WriteFileTool())
    registry.register(EditFileTool())
    registry.register(BashTool())
    registry.register(TodoWriteTool())
    registry.register(WebSearchTool(settings.firecrawl_api_key))
    registry.register(WebFetchTool(settings.firecrawl_api_key, settings.max_web_content_length))
    registry.register(SubAgentTool(agent_factory))
    return registry


def build_llm(settings: Settings) -> LLMClient:
    """Create the shared LLM client from settings."""
    return OpenAIClient(
        api_key=settings.api_key,
        model=settings.model,
        base_url=settings.base_url,
        max_tokens=settings.max_tokens,
    )


def build_agent(
    settings: Settings,
    registry: ToolRegistry,
    renderer: Renderer | None = None,
    llm: LLMClient | None = None,
) -> Agent:
    if llm is None:
        llm = build_llm(settings)
    # Deterministic post-reply verification is opt-in: an empty command keeps
    # the historical behavior (no Verifier constructed, no checks run).
    verification_command = settings.verification_command.strip()
    verifier = (
        Verifier(timeout_seconds=settings.verification_timeout_seconds)
        if verification_command
        else None
    )
    return Agent(
        llm=llm,
        registry=registry,
        settings=settings,
        renderer=renderer,
        verifier=verifier,
        verification_command=verification_command,
    )


def build_effective_prompt(prompt: str, rlm_controller: RLMController | None = None) -> str:
    """Optionally prepend a bounded RLM execution brief to one prompt."""
    if rlm_controller is None:
        return prompt
    rlm_result = rlm_controller.run(prompt)
    if not rlm_result.brief:
        return prompt
    return f"Execution brief:\n{rlm_result.brief}\n\nNow execute the task: {prompt}"


def resolve_settings(args: argparse.Namespace) -> Settings:
    """Load settings and apply CLI overrides + env var fallbacks."""
    settings = Settings()

    # Fallback: OPENROUTER_API_KEY -> AGENT_API_KEY
    if not settings.api_key:
        settings.api_key = os.environ.get("OPENROUTER_API_KEY", "")

    # Fallback: FIRECRAWL_API_KEY -> AGENT_FIRECRAWL_API_KEY
    if not settings.firecrawl_api_key:
        settings.firecrawl_api_key = os.environ.get("FIRECRAWL_API_KEY", "")

    # CLI overrides
    if args.model:
        settings.model = args.model
    if args.plan:
        settings.plan_mode = True
    if args.no_approval:
        settings.approval_mode = "never"

    return settings


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="trace",
        description="Trace Code — a terminal coding agent",
    )
    parser.add_argument("--model", default="", help="Override LLM model name")
    parser.add_argument("--plan", action="store_true", help="Start in plan mode")
    parser.add_argument(
        "--no-approval", action="store_true", help="Skip human approval for all tools"
    )
    parser.add_argument("--prompt", default="", help="Run a single prompt and exit")
    args = parser.parse_args()

    settings = resolve_settings(args)
    configure_logging(settings.log_level)

    renderer = Renderer(
        model=settings.model,
        plan_mode=settings.plan_mode,
        approval_mode=settings.approval_mode,
    )

    if not settings.api_key:
        renderer.error("No API key found. Set AGENT_API_KEY or OPENROUTER_API_KEY.")
        sys.exit(1)

    def agent_factory() -> Agent:
        sub_registry = build_registry(settings, agent_factory)
        return build_agent(settings, sub_registry)

    registry = build_registry(settings, agent_factory)
    llm = build_llm(settings)
    agent = build_agent(settings, registry, renderer=renderer, llm=llm)

    if args.prompt:
        # Single-shot mode
        context = AgentContext(
            plan_mode=settings.plan_mode,
            max_context_messages=settings.max_context_messages,
        )
        context.init_system_message()
        rlm_controller = RLMController(llm=llm, registry=registry) if settings.rlm_enabled else None
        agent.run(build_effective_prompt(args.prompt, rlm_controller), context=context)
    else:
        # Interactive REPL
        context = AgentContext(
            plan_mode=settings.plan_mode,
            max_context_messages=settings.max_context_messages,
        )
        context.init_system_message()
        repl = Repl(agent=agent, context=context, renderer=renderer)
        repl.run()


if __name__ == "__main__":
    main()
