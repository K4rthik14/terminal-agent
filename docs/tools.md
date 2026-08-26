# Tools Reference

Each tool implements the `Tool` abstract base class defined in `tools/base.py`. Tools are registered in `cli/main.py` (`build_registry`), which is the authoritative list of what ships in the default runtime.

Approval behavior below is for the default `auto` mode: **read-only** tools run without prompting; everything that can modify your system requires an explicit `[y/N]` approval. `AGENT_APPROVAL_MODE=always` prompts for every tool; `never` skips all prompts.

| Tool name | File | Read-only | Description |
|-----------|------|:---------:|-------------|
| `read_file` | `tools/file_read.py` | yes | Read a file from disk |
| `write_file` | `tools/file_write.py` | no | Create or overwrite a file |
| `edit_file` | `tools/file_edit.py` | no | Replace an exact string in a file |
| `bash` | `tools/bash.py` | no | Execute a shell command (30s timeout) |
| `todo_write` | `tools/todo.py` | yes | Replace the in-session todo list |
| `web_search` | `tools/web_search.py` | yes | Search the web (requires Firecrawl key) |
| `web_fetch` | `tools/web_fetch.py` | yes | Fetch a URL as readable text (requires Firecrawl key) |
| `task` | `tools/sub_agent.py` | no | Delegate to a child agent with a fresh isolated context (depth-capped at 2 levels) |

Notes:

- The model only sees tools selected by the context pipeline for the current goal, not necessarily the full registry.
- In plan mode the Executor blocks every non-read-only tool, including `task`.
- Web search/fetch fail with a clean error result if `AGENT_FIRECRAWL_API_KEY` is not configured.

## Adding a New Tool

1. Create `tools/your_tool.py` implementing `Tool`.
2. Register it in `build_registry` in `cli/main.py`.
3. Add its entry to this document.
4. Write a unit test in `tests/unit/`.
