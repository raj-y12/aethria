# reviewer (legacy)

The original three-persona Reviewer implementation. **Historical
compatibility code** — the current evidence-first Reviewer lives in
`backend/investment_analysis/` (ARCHITECTURE.md §3.1, ADR-0016). Retained
while migration is in progress; do not add new product behaviour here.

## Purpose

Evaluate a Scout discovery and emit a structured, scored assessment
(quality, realism, fundability) via one of three reviewer personas.

## Inputs

A completed `ScoutInfo` and the active fund thesis / fund config.

## Outputs

`ReviewerOutput` (see `schema.py`): scores, rationale, risks.

## Responsibilities

- `base.py`: shared reviewer prompt/response handling, founder and
  regulatory grounding guards (via `context`).
- `reviewer.py`, `skeptical.py`, `opportunist.py`: the three legacy personas.
- `gap_retrieval.py`: gap-triggered supplemental retrieval when Scout's
  factual packet is thin.
- `structured_signals_clamp.py`: evidence-clamping for structured signals
  (currently has no production caller outside its own test — flagged as
  possibly-dead legacy code, not deleted per repository policy).

## Non-responsibilities

- Must not import Scout internals (only Scout's public `ScoutInfo` output).
- Does not decide INVEST/PASS/MONITOR — that's `partner/` (legacy) or
  `investment_analysis/` (current).

## Dependencies

`research` (reference verification), `context` (grounding guards, recency),
`services.scoring`, `utils.openai_client`.

## Public API

Import from `reviewer` directly (`from reviewer import DefaultReviewer`).

## Testing

`tests/test_reviewer_gap_retrieval.py`,
`tests/test_reviewer_structured_signals_clamp.py`,
`tests/test_legacy_reviewer_regulatory_context.py`.
