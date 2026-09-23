# investment_analysis

The authoritative Reviewer + Partner runtime path (ARCHITECTURE.md §3.1,
ADR-0016). The retired `reviewer/` and `partner/` executors have been removed.

## Architecture: why this isn't `reviewer/` + `partner/`

ADR-0016 didn't relocate the old Reviewer and Partner engines — it **merged**
them into one transactional sequence on purpose. Reviewer and Partner are
still two distinct reasoning phases, but they intentionally execute inside a
single service (`service.py::analyze`), not as two independently orchestrated
agents:

1. Prepare the tenant's factual evidence snapshot.
2. **Reviewer phase**: propose cited dimension scores, reasoning units, risks,
   unknowns, diligence priorities. May request one bounded research pass.
3. **Validation**: Reviewer's proposal is checked against evidence policy —
   each score is retained, capped, or withheld — *before* Partner ever sees
   it. Partner never receives a raw, unvalidated Reviewer claim.
4. **Partner phase**: reads the *validated* review and chooses ADVANCE / PASS
   / MONITOR / MORE_DILIGENCE. Partner is deliberately **not** an
   independently orchestrated live agent — it has no entrypoint that runs
   without a review immediately preceding it in the same transaction.

This buys a specific guarantee this system needs and a plain two-service
pipeline wouldn't: *this* Partner decision came from *this* Reviewer
assessment, against *this* evidence snapshot, after *this* validation, in one
transaction — not a Partner call against a Reviewer result computed
independently, possibly minutes earlier, against evidence that has since
changed. `analyze()` has no clean functional cut between the two phases:
Partner's phase directly consumes local state (`review`, `validation`,
`admitted_snapshot`, `criteria`, `assessment_aliases`) built mid-function by
Reviewer's phase, per ADR-0016's frozen-comparison tests.

**Consequence**: splitting this service into independent Reviewer and
Partner packages would be a semantic architecture change — undoing the
"exactly one validated Reviewer output feeds exactly one Partner decision,
atomically" invariant ADR-0016 exists to establish — not merely a directory
refactor. Don't do it to make the file tree match a generic three-agent
template; propose an ADR amendment first if the coupling itself is ever
wrong.

Historical Reviewer and Partner records remain readable through one-way
projections; no historical engine is needed to execute a new judgement.

## Purpose

One evidence-first review producing cited reasoning units, proposed
dimension scores with rationale, risks, unknowns and diligence priorities;
then a genuine Partner decision read from the completed, validated review.

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
  withholds each proposed score. Zero effective confidence withholds the score
  and blocks advancement. It also removes Partner rationale lines that
  cite a dimension score contradicted by validation; current-result reads apply
  the same check to historical saved prose without changing immutable records.
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
- Does not import retired Reviewer, Partner, or deterministic scorer internals.

## Dependencies

`context`, `research`, `evidence`, `identity`, `services.scoring`,
`fund_thesis`.

## Public API

Import from `investment_analysis` directly for the small, deliberate public
surface (`analyze`, `AnalysisBlocked`, `AnalysisResult`,
`CompletedAnalysisStage`). Import `InvestmentAnalysisRepository` directly from
`investment_analysis.repository`, as the runtime entry points do. This concrete
repository owns current-result reads, failed-refresh history and atomic
publication. Its private publisher requires a completed `AnalysisResult` and a
frozen evidence clock; it cannot execute a historical evaluator (ADR-0017).

## Testing

`tests/investment_analysis/` (repository contracts, including
`test_baseline_comparison.py`, which pins the ADR-0016 frozen comparisons)
and the shared-analysis coverage across `tests/evaluation_v2/`.
