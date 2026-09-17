# scout

The Scout layer: discovers real, verifiable startup companies via the
retrieval chain plus OpenAI structuring (ARCHITECTURE.md §3.1).

## Purpose

Given a fund thesis and a chosen persona, find candidate companies and
produce a cited, evidence-grounded `ScoutInfo` payload — never a hypothetical
or fabricated company.

## Inputs

`user_id`, active fund thesis, persona (`market_driven`, `builder_technical`,
`pain_point`, `contrarian`), and optional on-demand lookup target.

## Outputs

`ScoutInfo` (see `models.py`): company facts, financials, references, and
handoff trace — never a review or decision.

## Responsibilities

- Persona-driven discovery query construction (`tools/discovery_queries.py`).
- Calling `research` for search/scrape, then structuring results via OpenAI.
- Deterministic financial-values grounding (`tools/financials_grounding.py`)
  — a pass/fail source-citation gate, not an LLM judgment call.
- Writing the Scout stage of the agent-trace handoff.

## Non-responsibilities

- Does not review, score, or decide (`investment_analysis/`, legacy
  `reviewer/`, `partner/`).
- Does not own generic provider SDK wrappers (`research/`) or the retrieval
  cache (`retrieval_cache/`) — it calls them.
- Does not persist to Supabase directly (`legacy_supabase/`, `startups/`).

## Dependencies

`research` (retrieval chain), `context` (canonical scout-claim bridge),
`retrieval_cache`, `tenant_context`, `fund_thesis`.

## Public API

`scout/tools/` holds Scout-private tools (not reusable outside Scout — see
`scout/tools/__init__.py`). The engine/persona classes are in `engine.py`,
`scouts.py`, `base.py`.

## Testing

`tests/test_scout_discovery_queries.py`, `tests/test_financials_grounding.py`,
plus the broader scout coverage across `tests/`.
