"""Main agent loop orchestrator.

Responsibilities:
- Owns the primary run() loop for a single agent session.
- Receives user input, forwards to LLMClient, dispatches tool calls via Executor.
- Loops until the LLM produces a final response with no pending tool calls.
- Has no knowledge of rendering, transport, or provider-specific details.
"""
