# Trace Code

> An autonomous coding agent.

Trace Code is an AI coding agent that lives in your terminal. Give it a task in natural language and it reads your code, edits files, runs commands, and verifies results — asking for your approval before consequential actions.

Unlike traditional chat-based agents that continuously append conversation history, Trace Code rebuilds its prompt every iteration using a state-driven context pipeline, keeping context compact and interactions predictable.

---

# Quickstart

Install → Configure → Run → Give Trace Code a task.

## Prerequisites

- **Python 3.11 or newer**
- **[uv](https://docs.astral.sh/uv/)** (recommended) *or* plain `pip`
- An **LLM provider API key** (the default configuration uses [OpenRouter](https://openrouter.ai))

## 1. Install

```bash
git clone https://github.com/K4rthik14/terminal-agent.git
cd terminal-agent
uv sync
```

This creates a virtual environment and installs the `trace` command inside it.

Prefer plain pip?

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Verify the installation:

```bash
trace --help
```

(With uv you can also run it without activating: `uv run trace --help`.)

## 2. Configure

Trace Code needs one API key. Export it as an environment variable:

```bash
export AGENT_API_KEY="<your-api-key>"
```

`OPENROUTER_API_KEY` is also accepted. Alternatively, put it in a `.env` file in your project root:

```bash
cp .env.example .env   # then set AGENT_API_KEY in the file
```

The model works out of the box (`poolside/laguna-s-2.1:free` via OpenRouter). To use a different model:

```bash
export AGENT_MODEL="<model-name>"    # or pass --model on any command
```

Optional: set `AGENT_FIRECRAWL_API_KEY` to enable the web search/fetch tools.

## 3. Run

```bash
trace
```

This starts an interactive session:

- Type tasks at the `>` prompt.
- `/plan` toggles plan mode (read-only planning; write tools disabled).
- `Ctrl+C` interrupts, `Ctrl+D` exits.
- In the default approval mode, Trace Code asks before running commands or modifying files.

## 4. Give Trace Code a task

In an interactive session:

```text
> add input validation to scripts/upload.py and run its tests
```

Or run a single task non-interactively:

```bash
trace --prompt "explain what src/parser.py does in three sentences"
```

Useful flags:

| Flag | Effect |
| --- | --- |
| `--model MODEL` | Override the model for this session |
| `--plan` | Start in plan mode (no writes) |
| `--no-approval` | Skip approval prompts (use with care) |
| `--prompt TEXT` | Run one task, then exit |

---

# Configuration reference

All settings load from environment variables and/or a local `.env` file (never committed). CLI flags override both.

| Variable | Required | Purpose |
| --- | --- | --- |
| `AGENT_API_KEY` | Yes | LLM provider API key (`OPENROUTER_API_KEY` accepted) |
| `AGENT_MODEL` | No | Model name; built-in default if unset (`--model` overrides) |
| `AGENT_FIRECRAWL_API_KEY` | No | Enables web search/fetch tools |
| `AGENT_APPROVAL_MODE` | No | `auto` (default), `always`, or `never` |
| `AGENT_MAX_TOKENS` | No | Max tokens per LLM response |

See `.env.example` for the annotated list.

---

# Troubleshooting

**`No API key configured`**
Set `AGENT_API_KEY` in your environment or in a `.env` file in the directory where you run `trace`. See step 2 above.

**`trace: command not found`**
Your virtual environment is not active. Either activate it (`source .venv/bin/activate`) or run through uv (`uv run trace ...`).

**Provider error: `<model>` is not a valid model ID**
The configured model name was rejected by the provider. Check the exact model identifier and set it via `--model` or `AGENT_MODEL`.

**Python version error during installation**
Trace Code requires Python 3.11+. Check with `python3 --version`.

---

# Development

Work on Trace Code itself:

```bash
uv sync          # create/update the environment
uv run pytest    # run the test suite
```

---

# Overview

This project is a modular terminal coding agent that combines **context engineering**, **prompt orchestration**, **execution optimization**, **evaluation**, and **multi-agent orchestration** into a single extensible architecture.

---

# Architecture

```text
User
  │
  ▼
CLI
  │
  ▼
Agent
  │
  ▼
MultiAgentCoordinator
  │
  ├── Planner
  ├── Executor
  ├── Reviewer
  └── Researcher
        │
        ▼
Context Pipeline
  ├── ContextState
  ├── GoalExtractor
  ├── RelevantFileSelector
  ├── RelevantToolSelector
  ├── ConversationSelector
  ├── PromptBuilder
  ├── PromptOrchestrator
  └── ContextEvaluator
        │
        ▼
Execution Pipeline
  ├── LoopDetector
  ├── ToolScheduler
  └── Evaluation Harness
        │
        ▼
LLM
  │
  ▼
Tools
```

---

# Features

## Context Engineering

- ContextState
- Goal Extraction
- Relevant File Selection
- Relevant Tool Selection
- Conversation Selection
- Dynamic Prompt Construction
- Prompt Orchestration
- Context Evaluation

---

## Execution Optimization

- Loop Detection
- Tool Scheduling
- Human Approval
- Streaming Responses
- Function Calling

---

## Tooling

- File Read
- File Write
- File Edit
- Bash Execution
- Web Search
- Web Fetch
- Todo Management

---

## Evaluation

- Evaluation Harness
- Execution Metrics
- Context Diagnostics
- Tool Usage Statistics
- Loop Detection Metrics

---

## Multi-Agent Orchestration

- Planner Agent
- Executor Agent
- Reviewer Agent
- Research Agent

Each agent operates with its own isolated context while sharing the same underlying execution infrastructure.

---

# Project Structure

```text
terminal-agent/
│
├── agent/
├── cli/
├── config/
├── context/
├── evals/
├── llm/
├── orchestration/
├── rlm/
├── tools/
├── utils/
├── docs/
└── tests/
```

---

# Design Principles

- Modular architecture
- Separation of concerns
- State-driven context engineering
- Token-efficient prompt construction
- Extensible orchestration
- Independent components
- Production-oriented design
- Evaluation-first development

---

# Current Capabilities

- Streaming LLM responses
- Function calling
- Planning mode
- Human approval
- File operations
- Bash execution
- Web search
- Web fetch
- Context engineering pipeline
- Prompt orchestration
- Execution optimization
- Evaluation harness
- Multi-agent coordination

---

# Future Work

- Recursive Language Models (RLM)
- Recursive Self Improvement (RSI)
- Persistent Memory
- TerminalBench Evaluation
- Prompt Optimization
- Advanced Multi-Agent Collaboration
- Self-Improving Harness

---

# Tech Stack

- Python
- OpenAI Compatible APIs
- OpenRouter
- Rich
- Pydantic
- Pytest

---

# Philosophy

Rather than treating an AI coding agent as a chatbot, this project treats it as a modular **AI Agent Harness**, where context construction, prompt orchestration, execution, evaluation, and orchestration are independent systems that work together to support reliable autonomous coding workflows.
