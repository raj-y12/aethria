# Review of Direction 2 (Evidence-and-Decisions Rebuild) — Against the Audited Codebase

**Date:** 2026-07-15
**Context:** Direction 2 rebuilds the pipeline around claims → evidence → policy → decision, with agents as replaceable workers. It is being implemented now. This review endorses the direction and flags what the implementation must get right, grounded in the 2026-07-14 audit and latency work.

---

## Verdict

Direction 2 is the correct target. It subsumes the institutional-agent redesign (claim extraction / evidence assessment / policy evaluation is the workstream idea taken to its logical conclusion), fixes every red-team objection by construction (lifecycle-triggered enrichment kills the unbounded-cost trap; read-only Fund Intelligence kills auto-mutation; company/deal separation makes dedup structural), and — critically — **more of it already exists than the plan seems to assume.** The risk is not the vision; it's migration sequencing, a third verdict vocabulary, and re-introducing the latency mistakes we just diagnosed.

## What is already built (don't rebuild it)

The plan's "Evaluate against fund policy" stage is the **most complete** part of the target system today:

- **Versioned published policies** already exist: `publish_policy`, immutable policy versions, `policy_version_id` + `policy_hash` stamped into every scoring trail.
- **Deterministic, evidence-pointing scoring** already exists: `DeterministicScoringEngine` + `scoring_trails` (append-only, per-decision, with component-level reasoning). "Scores must point to the evidence used" is ~70% this engine's existing behavior.
- **Claim-extraction seed** exists: `services/scoring/extraction_layer.py` produces `structured_signals` — a normalized, auditable extraction payload. The claims layer should be v2 of this schema, not a new ontology.
- **Evidence-status seeds** exist: `field_provenance` (scout | reviewer_extraction | gap_retrieval | reviewer_text_infer) is a per-field provenance map; `operator_context` is already treated as untrusted founder-asserted material; `reference_verify` already classifies reachable/inconclusive/dead sources.
- **Identity seeds** exist: the resolver computes registrable domains, founder anchors, confidence, `NEEDS_REVIEW` status, and candidate lists — the "resolution queue" is a UI over states the resolver already emits.
- **Proposal governance** exists: meta prompt changes already flow through proposals → eval records → explicit promotion (`meta/prompt_gating.py`), with auto-apply off by default. Fund Intelligence is mostly *extending* this gate to the reweighter and calibrator (which currently self-apply) and adding the proposal surfaces.

## Six things the implementation must get right

### 1. Do not mint a third verdict vocabulary
The plan says "advance, monitor, or pass." The codebase already carries INVEST/PASS/MONITOR **and** legacy YES/NO/MAYBE, and that duality caused two of the audit's confirmed bugs (Bugs 1 and 4). Adding advance/monitor/pass makes three. Pick ONE canonical enum for the recommendation, keep human rulings as their own explicitly separate enum, and write adapters only at the DB-column and export boundaries. This is the cheapest catastrophic-mistake-avoidance in the whole migration.

### 2. Sequence the migration around the Postgres refactor
A plain-Postgres migration (off supabase-py/PostgREST) is already planned. The **company/deal split is the largest schema change in Direction 2** — doing it on the Supabase schema and then migrating to Postgres means paying for two painful migrations. Sequence:

1. **Canonical identity first** — registrable domain as primary key, aliases table. Smallest blast radius, and it directly fixes audit Bug 2 (duplicate lookups keyed on `display_name`). Ships value before any conceptual change is visible.
2. **Evidence-status tagging second** — additive: stamp claim status (verified / founder-asserted / inferred / contradicted / stale / missing) onto the existing `structured_signals` schema. No behavior change; the memo can start *rendering* evidence status while personas still produce it.
3. **Reviewer split third** — claim extraction / evidence assessment / policy evaluation replacing personas. The big one; see #4 and #6.
4. **Company/deal split last, inside the Postgres refactor** — one migration, not two.

### 3. Carry the latency plan into the new pipeline from day one
The new pipeline has more named stages than the old one. Implemented naively (each stage = a sequential LLM pass + a Supabase read-modify-write), it will be *slower* than the pipeline we just diagnosed as too slow. Bake in the latency doc's rules as design constraints: retrieval calls parallel by default, stage handoffs pass in-memory objects (persist alongside, never re-read-what-you-just-wrote), claim extraction + evidence assessment as one structured call or concurrent per-source calls, policy evaluation fully deterministic (it already is). Add the Phase-0 stage-duration histograms to the *new* stages from their first commit.

### 4. Scope the claims ontology ruthlessly (v1 = closed taxonomy)
"Collect claims and evidence" is the genuinely novel, genuinely hard layer — everything else in Direction 2 is rearrangement of things that exist. The failure modes are an ontology too rigid to represent real claims or so loose everything becomes "inferred." V1 should be a **closed taxonomy** lifted from the extraction layer's existing signal fields (traction, team history, market size, funding, technical architecture, customer adoption) with the six status values — and nothing user-extensible until the closed set survives contact with real deals. Contradiction detection starts as exact-field conflict between sources (deck says $2M ARR, external source says $500K), not semantic contradiction.

### 5. Keep the frontend renderable across BOTH artifact generations
The memo, `AssessmentScorecard`, queue verdict lines, and `types/startup.ts` all render persona-shaped reviews (`reviews[]` with Default/Skeptical/Opportunist rows). Old rows will exist forever. Stamp a `review_schema_version` on rows (the codebase already stamps `prompt_version` and `policy_version_id` — same pattern), and either (a) keep a compatibility adapter that maps workstream/claim output into the legacy `reviews[]` shape during transition, or (b) branch the renderer on schema version. Do NOT rewrite old rows into the new shape — they are decision records; their form at decision time is part of the audit trail.

### 6. Name the concrete violations the new design fixes — and verify them fixed
Two current behaviors are exactly what "must not silently convert weak evidence into a confident decision" prohibits; they should become acceptance tests for the new policy layer:
- **Unscored-dimension inheritance:** when a dimension has no evidence, the structured scorer stamps the overall score onto it (`reviewer/engine.py:_apply_structured_scoring`) — missing evidence silently becomes a neutral-to-good number. Under Direction 2 this must surface as `missing` evidence + an explicit uncertainty note, never an inherited score.
- **Uncited founder labels:** persona reviewers emit "strong technical founders" with no citation. Under the evidence standard this must render as an inference with supporting facts or `[MISSING]`.

## Two smaller flags

- **The persona sunset needs a data story for the meta layer.** `scout_type` weights, reviewer calibration history, and the eval set are all persona-keyed. Decide explicitly whether that history is discarded, frozen as legacy, or mapped to sourcing strategies — silent reinterpretation of old calibration data under new semantics would corrupt Fund Intelligence's first proposals.
- **The resolution queue is a real UI surface, plan it.** "Ambiguous matches should never be silently merged" implies a human queue with merge/split actions and an audit trail of identity decisions. Small but new; it fits the Flow docket idiom (a second register, like the escalation queue).

## Bottom line

Build it. The order that de-risks it: canonical identity → evidence tagging → reviewer split → company/deal split (inside the Postgres refactor), with one canonical recommendation enum and the latency constraints as day-one design rules. The two acceptance tests in §6 are how we'll know the rebuild delivered its central promise rather than reorganizing the same behavior under better names.
