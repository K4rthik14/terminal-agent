"""OpenAI-compatible LLM client implementation.

Responsibilities:
- Implements LLMClient for the OpenAI API (and compatible endpoints).
- Maps internal Message / ToolCall types to OpenAI request shapes.
- Maps OpenAI response shapes back to internal types.
- Never imported by agent core directly — injected via main.py factory.
"""

from collections.abc import Iterator
from typing import Any

from openai import OpenAI

from config.defaults import OPENROUTER_BASE_URL
from llm.base import LLMClient
from llm.streaming import parse_openai_stream
from utils.errors import LLMError
from utils.types import MessageList, StreamEvent


class OpenAIClient(LLMClient):
    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str | None = OPENROUTER_BASE_URL,
        max_tokens: int = 4096,
        app_name: str | None = None,
        site_url: str | None = None,
    ):
        self._model = model
        self._max_tokens = max_tokens

        default_headers: dict[str, str] = {
            "Authorization": f"Bearer {api_key}",
        }
        if app_name:
            default_headers["X-Title"] = app_name
        if site_url:
            default_headers["HTTP-Referer"] = site_url

        self._client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            default_headers=default_headers or None,
        )

    def stream(
        self,
        messages: MessageList,
        tool_schemas: list[dict[str, Any]],
    ) -> Iterator[StreamEvent]:
        """Stream a response from the OpenAI-compatible API, yielding StreamEvent objects.

        Transport failures raised while creating the request or while iterating
        the response stream are normalized to LLMError (preserving the original
        message for transient-error classification), so the bounded retry path
        handles both instead of leaking raw SDK exceptions.
        """
        try:
            kwargs: dict[str, Any] = dict(
                model=self._model,
                messages=messages,
                max_tokens=self._max_tokens,
                stream=True,
            )
            if tool_schemas:
                kwargs["tools"] = tool_schemas

            raw_stream = self._client.chat.completions.create(**kwargs)
            yield from parse_openai_stream(raw_stream)
        except LLMError:
            raise
        except Exception as exc:
            raise LLMError(f"OpenAI API request failed: {exc}") from exc
