"""Streaming response handler.

Responsibilities:
- Accepts a raw provider stream and iterates its chunks.
- Assembles token deltas into a coherent response incrementally.
- Emits structured stream events (token, tool_call_start, tool_call_delta, done).
- Provider-agnostic once the raw stream object is handed in by a concrete client.
"""

from collections.abc import Iterator

from utils.types import StreamEvent


def parse_openai_stream(stream) -> Iterator[StreamEvent]:
    """Parse a raw OpenAI-compatible SDK stream into StreamEvent objects.

    Yields:
        StreamEvent(type="token")           for content deltas
        StreamEvent(type="tool_call_delta") for tool call argument deltas
        StreamEvent(type="done")            when the stream finishes
    """
    for chunk in stream:
        choice = chunk.choices[0]

        # Content token delta
        if choice.delta.content:
            yield StreamEvent(type="token", content=choice.delta.content)

        # Tool call deltas
        for tc in choice.delta.tool_calls or []:
            yield StreamEvent(
                type="tool_call_delta",
                tool_call_index=tc.index,
                tool_call_id=tc.id or "",
                tool_call_name=tc.function.name or "",
                content=tc.function.arguments or "",
            )

        # Stream finished
        if choice.finish_reason:
            yield StreamEvent(type="done", finish_reason=choice.finish_reason)
