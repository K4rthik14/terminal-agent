"""Web fetch tool.

Responsibilities:
- Performs an HTTP GET for a given URL.
- Strips HTML and converts the response body to clean markdown text.
- Truncates or paginates large responses to fit context limits.
"""

import requests
from typing import Any

from config.defaults import MAX_WEB_CONTENT_LENGTH
from tools.base import Tool
from utils.types import ToolResult


class WebFetchTool(Tool):
    name = "web_fetch"
    description = "Fetch a URL and return its content as readable markdown text."
    parameters = {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "URL to fetch."},
        },
        "required": ["url"],
    }
    is_read_only = True

    def __init__(self, firecrawl_api_key: str, max_length: int = MAX_WEB_CONTENT_LENGTH) -> None:
        self._api_key = firecrawl_api_key
        self._max_length = max_length

    def run(self, args: dict[str, Any]) -> ToolResult:
        try:
            response = requests.post(
                "https://api.firecrawl.dev/v1/scrape",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={"url": args["url"], "formats": ["markdown"]},
                timeout=30,
            )
            response.raise_for_status()
            content = response.json()["data"]["markdown"]
            return ToolResult(tool_call_id="", content=content[:self._max_length])
        except Exception as e:
            return ToolResult(tool_call_id="", content=f"Error fetching URL: {e}", is_error=True)
