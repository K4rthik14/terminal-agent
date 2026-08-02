"""OpenAI-compatible LLM client implementation.

Responsibilities:
- Implements LLMClient for the OpenAI API (and compatible endpoints).
- Maps internal Message / ToolCall types to OpenAI request shapes.
- Maps OpenAI response shapes back to internal types.
- Never imported by agent core directly — injected via main.py factory.
"""
