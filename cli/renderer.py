"""Rich-based terminal output renderer.

Responsibilities:
- All terminal formatting lives here and nowhere else.
- Renders: streaming tokens, tool call previews, approval prompts,
  plan display, todo lists, errors, and final responses.
- Uses the `rich` library for panels, syntax highlighting, and spinners.
- Accepts structured data types from utils/types.py — never raw strings from agent logic.
"""
