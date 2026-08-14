# Step 13 — production/local-realistic benchmark report

## Status

This was a measurement-only pass. No production behavior, prompts, schemas,
thresholds, cache logic, contradiction gates, personas, or connectors were
changed.

## Benchmark readiness and limitation

The repository already exposes bounded instrumentation for the requested
measurements:

| Measurement | Existing instrumentation | Result in this pass |
| --- | --- | --- |
| Cache hits/misses/provider calls avoided/duplicates | `aethria_retrieval_cache_events_total` | Instrumented; no live observations |
| Exa/Firecrawl/DDG requests, latency, results, credits | retrieval provider metrics | Instrumented; no provider calls |
| Model tokens by stage/model/provider | `aethria_model_provider_tokens_total` | Instrumented; no live LLM calls |
| Pipeline/stage latency | pipeline stage histograms | Instrumented; no end-to-end run |
| DB queries/rows/result bytes/large reads | DB profiler metrics | Instrumented; no benchmark dataset |
| Contradiction behavior | contradiction-gate and canonical-context tests | Deterministic test coverage only |
| Legacy dependence | Step 11/12 context and compatibility tests | Classified, not production-sampled |

The running local Postgres container is `aethria-postgres-1`, database
`aethria_test`. It contains the schema but zero rows in `startups`,
`companies`, `opportunities`, `claims`, `evidence_artifacts`,
`evaluation_runs`, `recommendations`, and `human_rulings`. Provider and LLM
credentials were also unavailable. Therefore no per-company, cold/warm, or
cost result is reported here.

## Representative cases

The existing test corpus provides deterministic correctness fixtures for Manna
Air Delivery (regulatory/operational), founder evidence, source-grounded
funding/market/traction claims, sparse evidence, contradiction handling, and
persona payload behavior. These are suitable correctness fixtures, but they are
not production benchmark runs and are not presented as latency or cost data.

## What can be concluded now

- Retrieval cache hit, miss, provider-call-avoided, stale-refresh, failure, and
  duplicate-suppression events are already recorded.
- Provider requests, result counts, latency, and reported credits are already
  recorded for Exa, Firecrawl, and DuckDuckGo fallback labels.
- Reviewer token usage is accumulated per persona and recorded through the
  existing cost controller; the Reviewer retry path exposes finish reason and
  total/reasoning token diagnostics in logs.
- Pipeline stage and database result metrics are available without tenant
  labels, preserving bounded metric cardinality.
- Canonical coverage and legacy fallback are visible in ContextAssembler packet
  fields (`has_canonical_coverage`, `fallback`, `missing_information`) and the
  Step 11/12 compatibility tests.

## Correctness fixture results

The focused measurement/correctness suite produced:

```text
32 passed, 1 warning
```

It covered metrics exposition, cost/token recording, retrieval cache behavior,
Manna regulatory grounding, contradiction gates, and existing canonical
context behavior. The full Step 12 verification immediately before this pass
was `2157 passed, 21 skipped`; the unrelated untracked
`backend/tests/test_db_telemetry.py` import issue remains excluded.

## Required real benchmark run

The next measurement run should use six tenant-scoped opportunities: Manna,
founder-heavy, traction-heavy, market-heavy, sparse-evidence, and
persona-disagreement. For each, capture a cold run and an identical warm run,
then export Prometheus deltas by run identifier outside the application:

1. retrieval provider requests, cache events, latency, credits, and duplicate
   suppression;
2. evidence artifacts/items, claims, claim links, and criterion coverage;
3. per-persona prompt characters, input/output/reasoning tokens, finish reason,
   retries, duration, and cost;
4. retrieval, Scout, Reviewer, Partner, and memo wall-clock stages;
5. contradiction-gate corrections and final memo/Partner consistency;
6. compatibility fields consulted and canonical fallback rates;
7. DB query count, large-result count, rows, bytes, and duration.

## Option 2 decision gate

There is not enough real data to justify Reviewer Option 2. The existing
three-persona architecture should remain unchanged until the benchmark shows
material Reviewer cost, retry, latency, or duplicated-context pressure.

## Architectural issues uncovered

No new architectural issue was discovered. The actionable gap is operational:
the benchmark dataset/run harness and an authenticated provider/LLM execution
environment are not yet available. Adding instrumentation automatically would
be unnecessary because the required metric families already exist.
