"""Streaming response handler.

Responsibilities:
- Accepts a raw provider stream and iterates its chunks.
- Assembles token deltas into a coherent response incrementally.
- Emits structured stream events (token, tool_call_start, tool_call_delta, done).
- Provider-agnostic once the raw stream object is handed in by a concrete client.
"""
