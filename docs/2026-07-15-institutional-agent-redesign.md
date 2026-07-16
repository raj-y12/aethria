# Agent Roles Are Not Institutional Standard — Diagnosis and Redesign

**Date:** 2026-07-15
**Trigger:** the observation that the scout/reviewer/partner agents don't mirror how an institutional fund actually operates. This doc agrees, says precisely where, and proposes the redesign.

---

## What's already institutional-grade (don't touch)

Credit where due — the *process machinery* around the agents is more institutional than most of the category:

- **Versioned, auditable policy** (partner rules as versioned JSON, immutable published scoring policies, policy hashes).
- **Full decision provenance** (agent_trace across handoffs, append-only scoring trails, conviction_state decision history, prompt-version hashes on every artifact).
- **A real escalation construct** (human_review_required → ruling → recorded override with rationale) and a **mandate-exception process** (strong company, off-thesis → held for explicit IC exception). That's a genuine IC concept, correctly modeled.
- **Prompt-change governance** (meta prompt mutations are gated behind eval records and explicit promotion, auto-apply off by default).

The problem is not the process spine. It's **who the agents are**.

## Where it's not institutional: personas instead of roles

### Scouts: personalities where a fund has coverage
Market-Driven / Builder-Technical / Pain-Point / Contrarian are **prompt personalities**, not sourcing roles. No institutional fund staffs origination as four temperaments; it staffs **coverage** — a person owns a sector/stage/geo beat derived from the fund's mandate, is accountable for a market map of that beat, and sources against defined channels. "Contrarian" is a *strategy within a beat* ("non-consensus within our mandate"), not a beat.

Concretely wrong today: the four scouts all search the same undifferentiated space with different vibes, so their output overlaps and the meta-reweighter is left tuning *which personality gets more turns* — a knob no real fund has.

### Reviewers: three attitudes re-scoring the same rubric
Default / Skeptical / Opportunist is **simulated disagreement, not independent diligence**. All three score the identical five dimensions from the identical input with different dispositions; the "consensus" is a majority vote of moods, and `score_variance` measures prompt-induced spread, not evidentiary conflict. An institutional analyst process is divided by **workstream, not temperament**: market diligence, team/founder diligence, product/technical diligence, business-model/traction diligence — each producing *findings with evidence*, which a deal lead then synthesizes. Disagreement in that world means *the evidence conflicts* (a signal worth escalating), not *the skeptical prompt was skeptical* (noise dressed as signal).

This is also exactly why the reviewer output violates the evidence-backed-founder standard: an attitude persona asked to score "execution 1–10" has nothing to cite, so it emits vibes ("strong technical founders"). A team-diligence workstream, whose only job is founder evidence, structurally can't.

### Partner: a threshold ladder where a fund has staged gates
The rule engine is well built, but it models the decision as one shot: scores in → INVEST/PASS/MONITOR out. Institutional decisions are **staged**: screen → partner review → IC, with different evidence bars at each gate, an assigned devil's advocate at IC, and a recorded vote. Aethria has the endpoints of this (auto rules at the bottom, human escalation at the top) but no middle, and nothing is framed as a *gate with an evidence bar* — a deal with thin team evidence should fail the IC gate for *that stated reason*, not receive a lower blended score.

## The redesign

Keep the pipeline shape (source → diligence → decide) and the process spine. Replace the personas:

**1. Scouts → coverage mandates.** Derive N coverage beats from the fund thesis (sectors × stage × geo). Each scout instance owns a beat: sources within it, maintains a lightweight market map for it (companies seen, clusters, what's missing), and reports coverage, not personality. "Contrarian" survives as a per-beat search strategy toggle. The meta-reweighter then tunes something a fund actually tunes — *allocation of sourcing attention across beats* — instead of personality airtime. (Mechanically small: scout prompts become thesis-beat-parameterized instead of four hardcoded personas; `scout_type` becomes `coverage_beat`.)

**2. Reviewers → diligence workstreams + a deal lead.** Four workstream agents — Market, Team/Founder, Product/Technical, Business Model & Traction — each returns *findings + cited evidence + a dimension score for its own workstream only* (the Team workstream is where the evidence-backed founder standard lives natively). A fifth synthesis step (the deal lead — can be deterministic-first like the partner) composes the memo, flags **evidentiary conflicts** between workstreams, and computes the blended score. Same LLM call count as today (3 → 4+~1), radically better artifact: every score traces to the workstream that owns it and the evidence it cited. `reviewer_disagreement` becomes "workstreams found conflicting evidence" — a real diligence signal — instead of "the moods diverged."

**3. Partner → explicit gates.** Reframe the existing rules as three named gates with evidence bars: **Screen** (auto: thesis fit + minimum evidence present), **Partner Review** (rules: scores/risks/contradictions — today's engine, nearly unchanged), **IC** (escalation: structured memo + auto-assigned devil's-advocate brief compiled from the most adverse workstream findings + recorded ruling). Deals fail gates *for stated evidentiary reasons*. The existing mandate-exception flow slots into IC untouched. The devil's-advocate brief is cheap — it's a selection over findings the workstreams already produced — and it's the single most "institutional-feeling" artifact this system could show a GP.

## Why this ordering of concerns is right

- It makes the **evidence-backed founder standard** structural instead of aspirational (a workstream that only does team diligence can be *required* to cite or say [MISSING]).
- It gives **institutional learning** its missing attribution: an override or a missed winner now maps to a workstream ("team diligence keeps underweighting repeat founders"), which is the granularity the meta-agent needs to calibrate anything meaningful.
- It converts the multi-agent design from a demo trope ("we have 7 AI personas!") into the actual org chart of a fund — which is the difference a GP notices in the first ten minutes.

## Migration reality check

- **Data model:** `scout_type` and `reviewer_type` literals are baked into models, storage projections, meta reweighting, and the frontend. This is a real migration, not a prompt swap — plan it with the legacy-enum cleanup from the audit (same class of change, do them together).
- **Do it before, not after, the feature roadmap:** every red-teamed feature (backtesting, institutional learning, founder dossiers) gets strictly better artifacts from workstream-structured reviews; building them on persona output bakes the vibes problem into more surfaces.
- **Cost:** neutral. Same order of LLM calls per deal; the synthesis/deal-lead step is deterministic-first with LLM only for conflict narration.
