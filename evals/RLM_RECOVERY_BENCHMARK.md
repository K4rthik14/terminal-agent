# Live OpenRouter trajectory-reflection benchmark

## Status

The benchmark now runs the production OpenRouter-compatible client through the real `Agent`, tool registry, verification loop, and `RLMReflector`. The LLM is not scripted. It uses 12 paired coding tasks in [`rlm_recovery_tasks.json`](rlm_recovery_tasks.json), each with a deliberately faulty starter workspace and a `pytest` acceptance test.

**Live benchmark results are not available yet.** The environment has no `AGENT_API_KEY`/`OPENROUTER_API_KEY` and no project `.env`, so no OpenRouter requests were made. All 12 starter workspaces were locally verified to fail their acceptance test before an agent run. This confirms the fixtures are recoverable test inputs, not that either agent mode repairs them.

## Run

After configuring an OpenRouter key and deciding to permit provider charges, run:

```bash
python -m evals.rlm_recovery_benchmark --allow-api-costs
```

The explicit flag is required because a full paired run makes 24 task runs plus any repair/reflection requests. The runner refuses to make provider calls without it and checks that the configured endpoint is OpenRouter. Each task/mode pair starts from identical files in a fresh temporary workspace. Verification clears bytecode and pytest caches before each run, disables bytecode writing and pytest's cache provider, and removes generated caches before the workspace-integrity check.

## Tasks and outcomes

The task set covers input normalization, empty input, off-by-one errors, case/whitespace handling, boolean conditions, numeric return contracts, collection ordering, string suffix boundaries, precision, and inclusive boundaries. The tests define the acceptance criteria; the starting implementations and prompts are checked in with the task data.

The report classifies a task as **helped** if RLM passes while baseline fails, **harmed** if baseline passes while RLM fails, and **no outcome change** otherwise. This classification is calculated from verifier outcomes, not assigned in advance.

## Metrics and limitations

The JSON output records per-task pass/recovery outcomes, agent status, root-agent verification attempts/passes/failures/errors, repair attempts, tool counts by name (including delegated agents), root-agent reflection calls/failures, counted LLM requests, fixture-integrity status, and elapsed execution time. Nested delegated-agent verification/reflection counters are not aggregated. Successful recovery rate is recoveries divided by runs with at least one verification failure; overall success rate uses all tasks. The runner rejects success if protected tests are changed, symlinks appear, or extra workspace files are left behind. It does not save prompts, tool output, verifier output, or model-generated text. Provider token usage is reported as unavailable: the current streaming client does not expose provider usage, and this benchmark does not substitute synthetic token estimates.

Live-model results will be stochastic and depend on the configured model, prompt behavior, and OpenRouter availability. A single paired run is a small exploratory evaluation, not evidence of general coding quality. Compare repeated runs and record the exact model/configuration before drawing conclusions. The earlier scripted three-task results are superseded and are not results for this live benchmark.
