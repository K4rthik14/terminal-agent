# Tools Reference

Each tool implements the `Tool` abstract base class defined in `tools/base.py`.

| Tool | File | Approval Required | Description |
|------|------|:-----------------:|-------------|
| `file_read` | `tools/file_read.py` | No | Read a file from disk |
| `file_write` | `tools/file_write.py` | On overwrite | Create or overwrite a file |
| `file_edit` | `tools/file_edit.py` | No | Apply targeted edits to a file |
| `bash` | `tools/bash.py` | Always | Execute a shell command |
| `web_search` | `tools/web_search.py` | No | Search the web via API |
| `web_fetch` | `tools/web_fetch.py` | No | Fetch and parse a URL |
| `todo` | `tools/todo.py` | No | Manage in-session todo list |
| `sub_agent` | `tools/sub_agent.py` | No | Spawn a delegated child agent |

## Adding a New Tool

1. Create `tools/your_tool.py` implementing `Tool`.
2. Register it in `tools/registry.py`.
3. Add its entry to this document.
4. Write a unit test in `tests/unit/test_your_tool.py`.
