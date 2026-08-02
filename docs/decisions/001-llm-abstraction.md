# ADR 001 — LLM Provider Abstraction

**Status:** Accepted  
**Date:** 2026-08-02

## Context

The agent must support multiple LLM providers (OpenAI, Anthropic) without
the core agent logic depending on any specific SDK.

## Decision

Define an abstract `LLMClient` in `llm/base.py`. Concrete implementations
(`openai_client.py`, `anthropic_client.py`) live alongside it but are never
imported by `agent/`. The correct client is instantiated in `cli/main.py` and
injected into the agent.

## Consequences

- Adding a new provider requires only a new file in `llm/` and a factory update in `cli/main.py`.
- The agent core and all tools are completely provider-agnostic.
- Testing the agent loop can use a mock `LLMClient` with no real API calls.
