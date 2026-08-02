"""Planning mode logic.

Responsibilities:
- When planning mode is active, prompts the LLM to produce a structured Plan
  before any tool execution begins.
- Returns a Plan dataclass that the agent loop consumes step-by-step.
- Decoupled from execution: planning never runs tools directly.
"""
