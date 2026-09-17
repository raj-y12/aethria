# context

Shared context-enrichment services consumed by Scout, the legacy Reviewer
(`backend/reviewer/`) and Partner (`backend/partner/`), and the current
shared evidence-first implementation (`backend/investment_analysis/`).

## Purpose

Assemble grounded, cited context — founder identity, regulatory posture,
commercial/competitive claims, contradiction detection, post-review
enrichment — without any one agent owning it privately. This package exists
*because* both the legacy and current review implementations, plus
`pipeline_runner.py`, `opportunity_pipeline.py`, and the storage layer, all
need the same context assembly.

## Inputs

Scout/review output dicts, a `user_id`, and (for regulatory/founder) company
identity fields.

## Outputs

Structured context blocks (`ContextAssembler` contract), derived claims, and
grounding-guard verdicts.

## Responsibilities

- `assembler.py`: the shared `ContextAssembler` / `CanonicalContextProvider`
  contract every provider below attaches through.
- `founder.py`, `regulatory.py`: identity resolution, grounding guards,
  claim derivation.
- `commercial_knowledge.py`, `competition_knowledge.py`, `scout_claims.py`:
  canonical scout-claim derivation and persistence.
- `contradiction_gate.py`: cross-checks Reviewer/Partner output against
  evidence.
- `conviction_state.py`: conviction-patch computation for the API read path.
- `scout_field_gaps.py`, `scout_post_review_enrichment.py`: post-review
  backfill of weak Scout fields — lives here (not `scout/tools/`) because
  the storage layer calls it directly when persisting a completed review.

## Non-responsibilities

- No LLM calls and no persistence of its own beyond what `scout_claims.py`
  explicitly does against the canonical evidence layer.
- Does not decide INVEST/PASS/MONITOR (that's Partner / the canonical
  evaluator).

## Dependencies

`tenant_context`, `research` (reference verification), `evidence` (canonical
claim/link models), `security.prompt_safety`.

## Public API

Import from `context` directly (`from context import build_founder_context`).
See `context/__init__.py` for the full re-export list.

## Testing

`tests/test_founder_context.py`, `tests/test_legacy_reviewer_regulatory_context.py`,
`tests/test_context_assembler.py`, `tests/test_contradiction_gate.py`,
`tests/test_conviction_state.py`, `tests/test_scout_claims.py`,
`tests/test_commercial_knowledge.py`, `tests/test_competition_knowledge.py`,
`tests/test_scout_post_review_enrichment.py`, `tests/test_step85_context_contract.py`.
