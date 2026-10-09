# Trajectory-reflection recovery benchmark

**Run:** `python -m evals.rlm_recovery_benchmark`
**Benchmark:** `trajectory-reflection-recovery-fault-injection-v1`
**Model:** deterministic scripted fake; no provider/API calls.
**Scope:** the real `Agent` loop, write tool, `pytest` verifier, and optional `RLMReflector`. The CLI pre-execution brief is intentionally excluded so this isolates failure reflection.

## Results

| Metric (3 tasks) | `AGENT_RLM_ENABLED=false` | `AGENT_RLM_ENABLED=true` |
| --- | ---: | ---: |
| Successful tasks / rate | 2 / 3 (66.7%) | 2 / 3 (66.7%) |
| Verification failures | 4 | 4 |
| Recovered after at least one failure | 2 | 2 |
| Repair attempts | 3 | 3 |
| Tool calls | 6 | 6 |
| Mean wall time per task | 0.689 s | 0.722 s |
| Reflection failures | 0 | 0 |
| Reflection calls | 0 | 3 |
| LLM calls, including reflection | 12 | 15 |
| Estimated synthetic tokens | 5,301 | 7,236 |

Execution time is the elapsed local run time, dominated by starting `pytest`; these small differences are not a reliable latency comparison. Token figures are only character-count / 4 estimates over synthetic prompts and completions, **not provider token usage**.

## Representative cases

| Task | RLM off | RLM on | Observation |
| --- | --- | --- | --- |
| `strip-before-lowercase` | Failed after repair | Recovered | The configured reflection strategy selected the correct `strip()` fix. |
| `even-negative-integers` | Recovered | Recovered | No outcome change; both repair paths used the same correct modulo check. |
| `zero-divisor-contract` | Recovered | Failed after repair | The scripted reflection strategy recommended `0`, contradicting the test's `None` contract; following it regressed the repair. |

## Interpretation and limits

On this *constructed* set the overall success rate and recovery count are tied: reflection changes which tasks pass rather than increasing aggregate success. It helps once, makes one repair worse, and has no effect once. It also adds three LLM calls and about 36.5% more estimated synthetic tokens here. There were no reflection parse/runtime failures.

This is a reproducible fault-injection/control-flow check, **not evidence that trajectory-based reflection improves a real model's coding ability**. The scripted client deliberately selects task-specific repair outcomes based on whether the real reflection text is present; therefore the helpful and harmful cases are examples of what good/bad advice can do, not independent model judgments. No API key was configured for this run, so a live-model paired experiment could not be performed. A live evaluation should repeat paired tasks across multiple seeds/runs and capture provider-reported usage.

No RLM architecture changes were indicated by this harness run. The benchmark clears workspace bytecode before each verification to prevent Python's timestamp/size-based `.pyc` cache from making a just-written repair appear not to have taken effect.
