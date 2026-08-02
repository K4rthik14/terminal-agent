"""Web search tool.

Responsibilities:
- Sends a search query to a configured search API.
- Returns structured results: list of (title, url, snippet) records.
- API provider and key are read from settings, not hardcoded.
"""

import requests
from typing import Any

from tools.base import Tool
from utils.types import ToolResult


class WebSearchTool(Tool):
    name = "web_search"
    description = "Search the web and return the top results (title, URL, description)."
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query."},
        },
        "required": ["query"],
    }
    is_read_only = True

    def __init__(self, firecrawl_api_key: str) -> None:
        self._api_key = firecrawl_api_key

    def run(self, args: dict[str, Any]) -> ToolResult:
        try:
            response = requests.post(
                "https://api.firecrawl.dev/v2/search",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={"query": args["query"], "limit": 5, "sources": ["web"]},
                timeout=30,
            )
            response.raise_for_status()
            results = response.json()["data"]["web"]
            text = "\n\n".join(
                f"{r['title']}\n{r['url']}\n{r.get('description', '')}" for r in results
            )
            return ToolResult(tool_call_id="", content=text)
        except Exception as e:
            return ToolResult(tool_call_id="", content=f"Error searching web: {e}", is_error=True)
