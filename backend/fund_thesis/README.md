# fund_thesis

The per-user investment mandate: the fund thesis gate described in
ARCHITECTURE.md §3.2.

## Purpose

Own the fund thesis document (raw text + parsed JSON + embedding), its
versions, activation, and rule-based/embedding alignment scoring against a
startup.

## Inputs

A `user_id` and, for writes, raw thesis text or a `FundConfig` (from
Settings). Reads go through `FundThesisRepository` (asyncpg) or the legacy
Supabase service client during the compatibility window.

## Outputs

`ActiveThesis` / `ActiveThesisMeta`, alignment scores/stats, and version
records (`create_fund_thesis_version_with_repository`, `activate_...`).

## Responsibilities

- Active-thesis lookup + short-lived cache (`FUND_THESIS_CACHE_TTL_SECONDS`).
- Bootstrap of the default thesis when none exists.
- OpenAI-backed parse + embed for new versions (`ops.py`).
- Rule-based and embedding-based alignment scoring.

## Non-responsibilities

- Does not gate the periodic pipeline itself (that's `pipeline_runner.py`,
  which calls `get_active_thesis` and fails closed per invariant #2).
- Does not own decision policy/thresholds (`resources/config/partner_rules/`).

## Dependencies

`tenant_context`, `legacy_supabase` (compatibility boundary only, during the
thesis write cutover), OpenAI SDK (`ops.py`).

## Public API

Import from `fund_thesis` directly — `core.py` / `ops.py` / `repository.py`
are an internal split. See `fund_thesis/__init__.py` for the full re-export
list.

## Testing

`tests/test_fund_thesis_*.py`, `tests/test_structured_thesis_fit.py`,
`tests/test_settings_fund_config.py`, `tests/thesis/`.
