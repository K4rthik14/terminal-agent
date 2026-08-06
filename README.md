# Terminal Agent

> A modular AI-powered terminal coding agent built with a production-oriented architecture inspired by modern coding assistants such as Claude Code, Codex CLI, and Gemini CLI.

---

## Overview

This project is a modular terminal coding agent that combines **context engineering**, **prompt orchestration**, **execution optimization**, **evaluation**, and **multi-agent orchestration** into a single extensible architecture.

Unlike traditional chat-based agents that continuously append conversation history, this project rebuilds the prompt for every iteration using a **state-driven context pipeline**, reducing unnecessary context growth and improving modularity.

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
├── evaluation/
├── llm/
├── orchestration/
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
