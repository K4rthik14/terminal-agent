# Architecture Overview

Reflex Code is a modular terminal coding agent. This file is a short map; `ARCHITECTURE.md` in this directory is the detailed source-of-truth description of the v0.1 runtime.

## Layers

| Layer | Package | Role |
|-------|---------|------|
| Surface | `cli/` | Argument parsing, composition root, REPL, rendering |
| Agent core | `agent/` | Agent loop, executor, approval gate, session context |
| Context engineering | `context/` | State-driven prompt construction, selection, loop detection, metrics |
| Model | `llm/` | OpenAI-compatible client, streaming, error normalization |
| Capabilities | `tools/` | Tool implementations, registry, sub-agent delegation |
| Reasoning (experimental) | `rlm/` | Opt-in read-only pre-execution brief |
| Orchestration (library) | `orchestration/` | Role-routed coordinator API (not wired into the CLI) |
| Evaluation | `evals/` | Task runner, judge, metrics |
| Verification | `verification/` | Deterministic command/test checks |
| Foundation | `utils/`, `config/` | Types, errors, logging, settings |

## Dependency Rules

Dependencies flow inward: `tools/`, `llm/`, `context/` depend on `utils/` and `config/`; they do not import each other or the agent. Two pragmatic exceptions exist in v0.1: `agent/agent.py` imports `cli.renderer.Renderer` for display injection, and `evals/runner.py` reuses the CLI composition helpers (`build_agent`, `build_registry`) so evaluations construct agents exactly like production. Nothing in `llm/` or `tools/` imports from `agent/`.
