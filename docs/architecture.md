# Architecture Overview

terminal-agent is a modular, extensible terminal coding agent designed for
production quality and research extensibility.

## Layers

| Layer | Package | Role |
|-------|---------|------|
| Surface | `cli/` | User input, rendering, REPL |
| Orchestration | `agent/` | Agent loop, planning, execution, approval |
| Model | `llm/` | LLM clients and streaming |
| Capabilities | `tools/` | Individual tool implementations |
| State | `agent/context.py` | Session-scoped mutable state |
| Foundation | `utils/`, `config/` | Types, errors, logging, settings |
| Future | `memory/` | Memory subsystem (Phase 2+) |

## Dependency Rule

Dependencies flow inward only. `cli/` → `agent/` → `llm/`, `tools/` → `utils/`.
Nothing imports from `cli/`. Nothing in `llm/` or `tools/` imports from `agent/`.

See `decisions/` for rationale behind major design choices.
