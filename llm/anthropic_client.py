"""Anthropic LLM client implementation.

Responsibilities:
- Implements LLMClient for the Anthropic Messages API.
- Maps internal Message / ToolCall types to Anthropic request shapes.
- Maps Anthropic response shapes back to internal types.
- Never imported by agent core directly — injected via main.py factory.
"""
