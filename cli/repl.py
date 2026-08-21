"""Interactive REPL loop.

Responsibilities:
- Manages the interactive session when no prompt is passed as a CLI argument.
- Handles multi-line input, input history, and graceful Ctrl+C / Ctrl+D exit.
- Calls agent.run() per turn and passes output to the Renderer.
- Does not contain any agent or LLM logic.
"""

from agent.agent import Agent
from agent.context import AgentContext
from cli.renderer import Renderer

# ANSI-styled prompts keep user input visually distinct from agent output and
# make plan mode unmistakable at a glance.
_PROMPT = "\x1b[1;36m>\x1b[0m "
_PLAN_PROMPT = "\x1b[1;35mplan>\x1b[0m "


class Repl:
    def __init__(self, agent: Agent, context: AgentContext, renderer: Renderer) -> None:
        self._agent = agent
        self._context = context
        self._renderer = renderer

    def run(self) -> None:
        """Start the interactive session. Blocks until Ctrl-C or Ctrl-D."""
        self._renderer.banner()
        while True:
            try:
                prompt_str = _PLAN_PROMPT if self._context.plan_mode else _PROMPT
                user_input = input(prompt_str)

                if not user_input.strip():
                    continue

                if user_input.strip() == "/plan":
                    self._context.plan_mode = not self._context.plan_mode
                    self._renderer.plan_mode_status(self._context.plan_mode)
                    continue

                self._agent.run(user_input, context=self._context)

            except KeyboardInterrupt:
                print()
                continue
            except EOFError:
                self._renderer.goodbye()
                break
