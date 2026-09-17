# semantic_evaluation

A provider-neutral, shadow-only semantic evaluation capability. It exists to
let Scout and `investment_analysis` ask an LLM-backed classifier questions
like "is this evidence relevant" or "does this excerpt support this claim,"
observe the answers, and build up enough evidence to decide — later,
deliberately, never automatically — whether that classifier is actually
worth trusting for anything real.

## The one invariant this package exists to guarantee

**While `rollout_mode=SHADOW` (the only mode currently implemented), nothing
written by this package is ever read to determine authoritative
Scout/Reviewer/Partner/Investment-Analysis behaviour.** Observations are
recorded for later human review and offline calibration only.

This is tested directly:
`tests/investment_analysis/test_semantic_evaluation_shadow_invariant.py`
calls `investment_analysis.service.analyze()` twice, with the mock provider
forced to opposite extremes (probability 0.00 vs 1.00), and asserts the
Partner decision and recommendation state are identical both times — while
also asserting two distinct records were actually persisted, so the test
can't pass vacuously because the shadow call never ran.

## Why this isn't wired the way `ModelGateway` is

`investment_analysis.model_gateway.ModelGateway` correctly **fails closed**
(`AnalysisBlocked`) — a missing model or exhausted budget must never let the
authoritative pipeline silently guess. Semantic evaluation is the opposite
case: it is non-authoritative by construction, so it **fails open**. A
provider outage, timeout, or exceeded rate cap becomes an explicit
`SemanticEvaluationStatus` (`SUCCESS` / `TIMEOUT` / `PROVIDER_ERROR` /
`BUDGET_SKIPPED` / `DISABLED`) that `evaluate()` returns — never an
exception. Callers of `evaluate()` need no try/except.

Authoritative callers don't call `evaluate()` directly, though — they call
`schedule_shadow_evaluation()`, which dispatches `evaluate()` as a background
`asyncio.Task` (the same fire-and-forget pattern already used throughout
this codebase — `jobs/worker.py`, `event_bus.py`, `api.py`'s background
samplers) and returns immediately. A slow or unavailable provider adds zero
latency to Scout → Reviewer → Partner. The returned `Task` exists only so
tests can `await` it for determinism; production code must never await it.

## Provider boundary

`providers/base.py` defines a small `Protocol`, mirroring
`research/search_providers.py`'s `SearchProvider` pattern. Public domain
concepts are always `SemanticQuestion` / `SemanticEvaluationInput` /
`SemanticEvaluationResult` — never a provider-specific name. Jev-specific
concepts, when `providers/jev.py` is implemented, stay inside that one file
and get translated into these shapes at the boundary, exactly like Exa/
Firecrawl payloads get normalised into `ProviderSearchResults` before
anything else sees them. Only `providers/mock.py` exists today
(`SEMANTIC_EVALUATION_PROVIDER=mock`, the default) — it is free, deterministic,
and is what proves the abstraction end-to-end before any paid provider exists.

## Evaluation types and versioning

Three types are defined (`SemanticEvaluationType`), each with exactly one
versioned definition in `definitions.py`:

- `EVIDENCE_RELEVANCE` — is a retrieved source actually about this company/claim.
- `CLAIM_SUPPORT` — does this evidence excerpt support this specific claim.
- `RESEARCH_USEFULNESS` — is more targeted research likely to change the answer.

Each definition carries an `evaluation_version` (human-managed, bumped when
deliberately republished — mirrors `resources/config/partner_rules/v{N}.json`)
and a `criteria_version` (an automatic `utils.prompt_version.hash_prompt()`
hash of the question text + labels — mirrors `REVIEWER_PROMPT_VERSION` in
`investment_analysis/prompts.py`). The hash catches accidental wording drift
even if a version bump is forgotten, so two persisted rows sharing an
`evaluation_version` are still guaranteed comparable.

## What gets persisted

`db/migrations/20260917120000_semantic_evaluations.sql` — one append-only
row per non-`DISABLED` call: identifiers (`evaluation_id`, `pipeline_run_id`,
`workflow_run_id`, `startup_id`/`opportunity_id`, `user_id`), what was asked
(`evaluation_type`, `evaluation_version`, `criteria_version`), what answered
(`provider`, `model`, `provider_model_version`), the **full probability
distribution** (not just the winning label — calibration needs the
distribution), `selected_answer`, `confidence`, `status`, `latency_ms`,
`tokens`, `estimated_cost_usd`, `error`, and `rollout_mode`. Reproducibility
without re-storing potentially sensitive or oversized content: `claim_ids`/
`source_ids` (references, not content) plus `input_digest` (a hash of the
exact input state+questions, so identical inputs are detectable without
storing them twice).

## Measuring whether a provider is actually good — not just self-consistent

**Agreement with today's deterministic rules is not the definition of
"better."** If a provider disagrees with `context.contradiction_gate` and
the provider is right, treating that disagreement as failure would prevent
discovering the improvement this capability exists to find. Any comparison
must keep three things distinct:

- **A** — the existing deterministic/legacy baseline (e.g. `contradiction_gate`).
- **B** — the provider's prediction.
- **C** — independent ground truth (a human label, or a later confirmed outcome).

Measure all three pairs — A vs C, B vs C, and A vs B only as a secondary,
non-decisive signal — never promote a provider merely because it imitates
today's rule. For probabilistic output, also check calibration: outcomes a
provider called ~0.8 should turn out correct roughly 80% of the time,
independent of whether that matches the deterministic baseline. Comparison
tooling should extend `evaluation/golden_set.py`'s existing corpus format
rather than inventing a second offline-measurement framework.

## Promotion — none of this is authoritative until all of these hold

- A minimum sample size logged in shadow mode per evaluation type (order of
  hundreds, not tens).
- An explicit, pre-agreed accuracy/calibration threshold against ground
  truth (C above) — set per evaluation type, since the acceptable error cost
  differs (a wrong "research usefulness" guess is cheaper than a wrong
  "claim support" guess).
- No systematic bias found across sector/stage/persona.
- Cost per call sustainable at production volume under its own budget
  envelope (not yet built — see below).
- A human sign-off, per evaluation type, that it's ready to move from an
  advisory signal shown to a reviewer to any live influence — which itself
  should start as a displayed signal, never a silent gate. Nothing here
  should ever be used to replace Reviewer/Partner reasoning, change a
  canonical score, change a recommendation, enforce hard fund policy, or
  silently remove a company from the pipeline.

## Non-responsibilities

- Not a source of authority while SHADOW (see invariant above).
- Does not write to `agent_trace` — that's the authoritative startup-row
  trace; mixing shadow-mode noise into it would blur the observability/
  authority line this package exists to hold.
- Does not enforce a real dollar budget yet. `SEMANTIC_EVALUATION_MAX_CALLS_PER_MINUTE`
  is a simple in-process rate cap, deliberately decoupled from any tenant's
  `CostController` budget so a runaway shadow loop can never compete with
  real Reviewer/Partner spend — it is a placeholder until a provider with
  real cost (Jev) exists, at which point a dedicated `CostController`
  envelope should replace it.

## What remains to implement for Jev

1. `providers/jev.py` implementing `SemanticEvaluationProvider`, translating
   Jev-specific request/response shapes into `SemanticEvaluationInput`/
   `SemanticEvaluationResult` at the boundary.
2. Jev-specific config (`SEMANTIC_EVALUATION_PROVIDER=jev`, credentials,
   model selection) registered in `env_config.py`.
3. A real dollar-cost budget envelope via `CostController`, replacing the
   in-process rate cap, since a paid provider must respect invariant #8
   (no model call where a rule works, and every call budget-gated).
4. Wiring `schedule_shadow_evaluation()` calls into the two remaining
   proposed call sites (`research/retrieval_grounding.py` for
   `EVIDENCE_RELEVANCE`; `context/contradiction_gate.py` or wherever the
   current path checks claim support, for `CLAIM_SUPPORT` at that second
   location) — only one call site (`investment_analysis/service.py`, for
   `CLAIM_SUPPORT`) is wired in this first pass.
5. The comparison/calibration tooling described above, once enough shadow
   volume exists to make it meaningful.
6. Whatever the promotion criteria above actually require, decided
   explicitly, per evaluation type, by a human — not inferred from this
   package existing.

## Testing

`tests/semantic_evaluation/` (models, mock provider, all five `evaluate()`
statuses, repository contract) and
`tests/investment_analysis/test_semantic_evaluation_shadow_invariant.py`
(the invariant proof described above).
