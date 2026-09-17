# partner (legacy)

The original rule-based Partner implementation. **Historical compatibility
code** — the current evidence-first Partner decision lives in
`backend/investment_analysis/` (ARCHITECTURE.md §3.1, ADR-0016).

## Purpose

Make an investment decision from a legacy Reviewer evaluation: rule-based,
deterministic, cost-disciplined.

## Inputs

A completed `ReviewerOutput` and the versioned decision policy
(`resources/config/partner_rules/`).

## Outputs

`PartnerInfo` / decision (ADVANCE / PASS / MONITOR / MORE_DILIGENCE, or the
legacy INVEST/PASS/MONITOR projection).

## Responsibilities

- `decision.py`: the deterministic decision function against versioned
  thresholds (invariant #3 — thresholds are data, never hardcoded here).
- `engine.py`: orchestrates the legacy decision + persistence for a cycle.
- `rationale.py`: human-readable rationale generation for the decision.

## Non-responsibilities

- Must not import Reviewer internals — only `ReviewerOutput`.
- Does not run search/scrape or own provider clients (`research/`).
- Does not compute scores itself beyond reading `utils.scoring` — score
  *production* is Reviewer's job.

## Dependencies

`context` (contradiction gate, compatibility projection), `utils.scoring`,
`utils.partner_codes`, `core.policy_resolver`.

## Public API

`decision.py`'s decision function and `engine.py`'s orchestration entrypoint.

## Testing

`tests/evaluation_v2/test_decision_safety_certification.py` and the broader
partner coverage across `tests/`.
