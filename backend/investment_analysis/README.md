# investment_analysis

The current, shared evidence-first Reviewer + Partner implementation
(ARCHITECTURE.md §3.1, ADR-0016) — supersedes the legacy `reviewer/` /
`partner/` packages for live traffic.

## Purpose

One evidence-first review producing cited reasoning units, proposed
dimension scores with rationale, risks, unknowns and diligence priorities;
then a genuine Partner decision read from the completed review.

## Inputs

Scout output, canonical evidence/claims, fund thesis, and (for Partner)
canonical evaluation output and portfolio context where relevant.

## Outputs

A shared analysis record (see `models.py`): validated criteria scores,
Partner recommendation, and provenance — persisted via `repository.py`.

## Responsibilities

- `stages.py` / `service.py`: the shared factual-preparation → review →
  validation → decision pipeline.
- `grounding.py`: evidence/source-corroboration checks feeding the review.
- `validation.py`: evidence/policy validation that retains, caps, or
  withholds each proposed score.
- `model_gateway.py`: the model-call boundary for this stage (uses
  `utils.openai_client`, not a direct SDK call).
- `mandate.py`: applies explicit fund exclusions to the tenant factual
  snapshot — never infers a sector/exclusion from free text.
- `projection.py`: legacy startup-shape projection for API/frontend
  compatibility (ADVANCE→INVEST, MORE_DILIGENCE→MONITOR).
- `repository.py`: the analysis persistence boundary.

## Non-responsibilities

- Does not run search/scrape (`research/`) or own the retrieval cache.
- Does not decide canonical policy (`services/scoring/`, `evaluation_v2/`) —
  it consumes the published policy, never hardcodes a threshold.
- Does not import legacy `reviewer/`/`partner/` internals, and vice versa.

## Dependencies

`context`, `research`, `evidence`, `identity`, `services.scoring`,
`fund_thesis`.

## Public API

`service.py` / `stages.py` are the orchestration entrypoints
`pipeline_runner.py` calls; `repository.py` is the persistence boundary.

## Testing

`tests/investment_analysis/` (repository contracts) and the shared-analysis
coverage across `tests/evaluation_v2/`.
