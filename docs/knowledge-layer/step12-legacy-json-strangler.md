# Step 12 — legacy JSON strangler boundary

The `startups` JSON columns remain compatibility projections for existing API,
UI, memo, audit, and historical consumers. They are no longer an implicit
authority boundary when canonical records or immutable evaluation snapshots are
available.

## Authority classification

| Field | Current classification | Step 12 treatment |
| --- | --- | --- |
| `scout_info` | compatibility/API projection; legacy-only narrative source for product, technical, competition, business model, location, references | canonical runtime adapter wins for covered funding, market/TAM, traction, founder, and regulatory paths; legacy fields retained |
| `review_info` | compatibility projection plus persona/audit snapshot; canonical evaluation/criterion judgment is authoritative where present | preserved for Partner, memo, API, and persona history; canonical context snapshot remains attached |
| `partner_info` | compatibility projection of recommendation/ruling/workflow state | canonical authority events remain the write-side source; existing JSON shape retained |
| `financials` | compatibility projection of grounded financial extraction and current memo display | no new authority introduced; empty/missing remains unknown |
| `agent_trace` | audit/history and handoff provenance | never used as canonical evidence or identity |
| `conviction_state` | compatibility/history projection for legacy conviction UI | historical decision history is append-only and not rewritten |
| `investment_memo_markdown` | current memo artifact/API projection | historical memo content is preserved; it does not redefine evaluation state |

## Runtime boundary

`compatibility_projection.project_scout_for_runtime()` is the explicit adapter
used at the Partner handoff. If the stored ReviewInfo contains supported
canonical context, funding stage, TAM, and traction values are projected from
those claims rather than trusted from conflicting Scout JSON. If coverage is
missing, the legacy values remain as a safe fallback. The adapter is
read-only, does not create claims, and does not mutate stored JSON.

The canonical-to-legacy authority projection remains the write-side boundary for
identity, evaluation, recommendation, ruling, memo, and workflow events. This
prevents compatibility JSON from flowing back into canonical identity, evidence,
claims, or evaluation state except through explicit ingestion paths.

## Still load-bearing legacy data

Solution and company narrative, product/technical narrative, competition,
business model, location, references, and some financial/memo display fields
remain load-bearing for compatibility or because canonical parity is incomplete.
They cannot be retired until a source-linked canonical model, parity tests, and
all consumer migrations exist.

## Read and historical semantics

No broad JSON read rewrite is included. Existing narrow list projections remain
the efficient queue path, while full JSON loads are retained where memo, audit,
persona, or compatibility payloads require them. Immutable evaluation snapshots
and Decision Cases remain historical authority; current compatibility JSON cannot
retroactively change them.
