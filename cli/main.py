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
import traceback
from argparse import RawDescriptionHelpFormatter

from pydantic import ValidationError

from agent.agent import Agent
from agent.context import AgentContext
from cli.renderer import Renderer
from cli.repl import Repl
from config.settings import API_KEY_ENV_VARS, MODEL_ENV_VAR, Settings
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
from utils.errors import AgentError, ConfigError
from utils.logging import configure_logging, get_logger
from verification.verifier import Verifier

logger = get_logger(__name__)

HELP_EPILOG = """\
examples:
  trace                                    start an interactive session
  trace --plan                             plan without applying changes
  trace --no-approval --prompt "fix the failing tests"
                                           run one task end-to-end, no prompts

environment:
  AGENT_API_KEY                            LLM provider API key (required);
                                           OPENROUTER_API_KEY also accepted
  AGENT_FIRECRAWL_API_KEY                  optional; enables web search/fetch
  AGENT_MODEL                              default model (--model overrides it)

Settings load from the environment and a local .env file.
"""


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


def invalid_config_message(exc: ValidationError) -> str:
    """Describe which configuration variables are invalid and how to fix them.

    Names only variable names and expected types — never echoes values,
    since environment values may contain secrets.
    """
    lines = []
    for error in exc.errors()[:5]:
        field = ".".join(str(part) for part in error.get("loc", ()))
        env_name = f"AGENT_{field.upper()}" if field else "environment"
        lines.append(f"  {env_name}: {error.get('msg', 'invalid value')}")
    details = "\n".join(lines) if lines else "  (unknown configuration error)"
    return (
        "Invalid configuration:\n"
        f"{details}\n"
        "\n"
        "Fix the value in your environment or .env file, then try again."
    )


def unexpected_error_message(exc: Exception) -> str:
    """Concise report for unexpected internal errors, with a debug escape hatch."""
    return (
        f"Unexpected error: {type(exc).__name__}: {exc}\n"
        "This looks like a bug in Trace Code. "
        "Re-run with AGENT_LOG_LEVEL=debug for a full traceback."
    )


def resolve_settings(args: argparse.Namespace) -> Settings:
    """Load settings and apply CLI overrides + env var fallbacks."""
    try:
        settings = Settings()
    except ValidationError as exc:
        raise ConfigError(invalid_config_message(exc)) from exc

    # Fallback: OPENROUTER_API_KEY -> AGENT_API_KEY
    if not settings.api_key:
        settings.api_key = os.environ.get("OPENROUTER_API_KEY", "")

    # Fallback: FIRECRAWL_API_KEY -> AGENT_FIRECRAWL_API_KEY
    if not settings.firecrawl_api_key:
        settings.firecrawl_api_key = os.environ.get("FIRECRAWL_API_KEY", "")

    # CLI overrides
    if args.model and args.model.strip():
        settings.model = args.model.strip()
    if args.plan:
        settings.plan_mode = True
    if args.no_approval:
        settings.approval_mode = "never"

    return settings


def missing_api_key_message() -> str:
    """Explain which configuration is missing and how to set it.

    Never includes or echoes any secret value — only variable names.
    """
    primary, fallback = API_KEY_ENV_VARS
    return (
        "No API key configured. Trace Code needs an LLM provider API key.\n"
        "\n"
        "Option 1 — environment variable:\n"
        f"  export {primary}=<your-api-key>\n"
        f"  ({fallback} is also accepted)\n"
        "\n"
        "Option 2 — .env file in your project root (see .env.example):\n"
        f"  {primary}=<your-api-key>\n"
    )


def missing_model_message() -> str:
    """Explain how to select a model when none is configured."""
    return (
        "No model configured. Trace Code needs an LLM model name.\n"
        "\n"
        "Option 1 — command line:\n"
        "  trace --model <model-name>\n"
        "\n"
        "Option 2 — environment variable:\n"
        f"  export {MODEL_ENV_VAR}=<model-name>\n"
        "\n"
        "Option 3 — .env file in your project root (see .env.example):\n"
        f"  {MODEL_ENV_VAR}=<model-name>\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="trace",
        description=(
            "Trace Code — an AI coding agent for your terminal.\n"
            "Starts an interactive session by default; use --prompt for one-shot tasks."
        ),
        epilog=HELP_EPILOG,
        formatter_class=RawDescriptionHelpFormatter,
    )
    parser.add_argument("--model", default="", help="LLM model to use (overrides AGENT_MODEL)")
    parser.add_argument(
        "--plan", action="store_true", help="plan only: write tools are disabled"
    )
    parser.add_argument(
        "--no-approval", action="store_true", help="run all tool calls without approval prompts"
    )
    parser.add_argument(
        "--prompt", default="", metavar="TEXT", help="run a single prompt, then exit"
    )
    args = parser.parse_args()

    try:
        settings = resolve_settings(args)
    except ConfigError as exc:
        # Invalid configuration values (wrong types, etc.) — no traceback needed.
        Renderer().error(str(exc))
        sys.exit(1)

    configure_logging(settings.log_level)

    renderer = Renderer(
        model=settings.model,
        plan_mode=settings.plan_mode,
        approval_mode=settings.approval_mode,
    )

    if not settings.api_key:
        renderer.error(missing_api_key_message())
        sys.exit(1)

    if not settings.model.strip():
        # Fail fast on an explicitly empty model rather than sending an invalid
        # request to the provider. Unset models keep the built-in default.
        renderer.error(missing_model_message())
        sys.exit(1)

    def agent_factory() -> Agent:
        sub_registry = build_registry(settings, agent_factory)
        return build_agent(settings, sub_registry)

    try:
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
            rlm_controller = (
                RLMController(llm=llm, registry=registry) if settings.rlm_enabled else None
            )
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
    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(130)
    except AgentError as exc:
        # Runtime failures (provider, RLM, etc.) already carry actionable
        # messages; render them concisely instead of a raw traceback.
        renderer.error(str(exc))
        sys.exit(1)
    except Exception as exc:
        renderer.error(unexpected_error_message(exc))
        if settings.log_level.lower() == "debug":
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
