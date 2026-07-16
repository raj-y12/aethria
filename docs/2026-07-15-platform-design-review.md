# Review — Evidence and Decision Platform Design (2026-07-15)

**Reviewing:** `docs/superpowers/specs/2026-07-15-evidence-decision-platform-design.md`
**Verdict:** **Approve with findings.** The architecture, domain model, phasing, and governance posture are right. The findings below are ranked; F1–F4 should be resolved in the spec (or in the Phase 0/1 implementation plans) before Phase 1 work starts — each one is a place where the design as written will produce a concrete bad outcome, not a stylistic preference.

## What the spec gets right (kept short deliberately)

Phase 0 (freeze unsafe learning, golden set, manifests) before any construction is the correct first move and wasn't in my review — good addition. Durable execution as Phase 1 fixes a real production defect (today's in-memory queues drop accepted lookups on restart). The domain model's sharpest ideas — Opportunity separate from Company, process_state separate from decision_state, `INSUFFICIENT_EVIDENCE` as a first-class recommendation, OverrideSignal *classification* ("not every override is a model failure"), claim supersession instead of mutation, the material-claim rule, confidence capped by identity confidence — are exactly the institutional substance the product was missing. §11.5 (prompt-injection defence) and the risks table are better than most production specs. The spec also correctly preserves the audit-validated parts of the current system (rule-first partner, versioned policy, hard runtime gates).

---

## Findings

### F1 (blocking) — The enum problem is reintroduced, not solved
§7.10 mints **ADVANCE / MONITOR / PASS / INSUFFICIENT_EVIDENCE**; §8.5/§16.4 use the same triple for rulings. Long-term, one shared vocabulary for recommendation and ruling is an *improvement*. But during migration **four vocabularies are alive simultaneously**: INVEST/PASS/MONITOR (partner_info), YES/NO/MAYBE (human_resolution + partner_decision column), the new triple, and the legacy `decision` field whose phantom attribute access already caused two confirmed production bugs (audit Bugs 1 and 4). The spec's compatibility projections (§17) are exactly where those bugs will recur.
**Required:** a normative enum-mapping table in §7 (every legacy value → new value, both directions), one adapter module as the only place mapping happens, and contract tests on the compatibility projections. Also state explicitly that new-world "MONITOR" (a ruling that activates service level 3) is not the same object as old-world "MONITOR" (a partner recommendation) even though the word matches.

### F2 (blocking) — No latency budget; Phase 1 can easily make dispatch *slower*
The pipeline grows from 3 stages to ~7 (identity → evidence plan → retrieval → extraction → verification → policy → recommendation), and Phase 1 puts a durable job boundary between stages. Durable queues claimed by polling workers add a poll-interval per hop — five hops at even a 2s poll interval is +10s of pure queue wait, on top of the 60–120s dispatch time we just spent a whole plan reducing. The spec measures latency (§19) but never budgets it, and never mentions the 2026-07-14 latency plan.
**Required:** (a) a stated per-stage latency budget and an end-to-end target for interactive lookups (suggest: first recommendation ≤ 45s at Phase 4 parity); (b) an explicit **interactive fast path** — a manual lookup executes the stage chain in-process with durable *checkpointing* (write the job records as you go) rather than durable *dispatch* (enqueue and wait) — background/monitor work uses the queue; (c) carry the latency plan's standing rules (parallel retrieval, in-memory handoffs, no read-what-you-just-wrote) into §9 as design constraints.

### F3 (blocking) — "Dual-write from Scout and Dispatch" (Phase 2) is not safely implementable as written
Supabase REST has no multi-table transactions. True dual-write (old startups row + new observation/company/opportunity records) under partial failure guarantees divergence, and §20.7's migration tests will pass in CI while production drifts.
**Required:** pick one authoritative side per phase. Recommended: new records are authoritative from Phase 2; the legacy `startups` row becomes a **projection maintained by an outbox consumer** (the outbox ships in Phase 1, so the machinery exists). "Dual-write" should be renamed to "write-new, project-legacy" in the spec so nobody implements the racy version.

### F4 (blocking) — Evidence snapshot immutability has a hole: claim `status` mutates in place
§7.9 snapshots "evidence snapshot hash and claim set," and §7.8 gives claims a supersession link (good) — but claim **status** (CURRENT → STALE/CONTRADICTED) transitions on the same row. A historical EvaluationRun referencing claim IDs will silently see today's statuses, violating §8.3's own promise that an old run "remains valid as a historical statement of what Aethria knew at that time."
**Required:** either snapshot claims by value (copy id + value + status + assertion class into the run's snapshot), or make status changes create a new claim version like every other change. Cheapest correct option: the snapshot stores `(claim_id, status_at_snapshot, assertion_class_at_snapshot)` — a few columns, no event sourcing.

### F5 — Coordinate Phase 1 with the planned Postgres migration, and don't build the job store on PostgREST
The infra plan (Oracle/Coolify, plain-Postgres refactor) is not mentioned anywhere in the spec. A lease/heartbeat job system through PostgREST REST calls is the clumsy version of a solved problem: `SELECT … FOR UPDATE SKIP LOCKED` + LISTEN/NOTIFY over a direct connection (asyncpg is already in the stack for the event backplane). Building agent_jobs on PostgREST first and re-plumbing it onto direct Postgres later means building the hardest Phase 1 component twice. Sequence the direct-Postgres connection *into* Phase 1, not after it.

### F6 — The audit's live P1/P2 bugs must not wait for their phase
The spec structurally obsoletes audit Bugs 5/6 (Phase 0 freeze; lifecycle levels) — fine. But Bug 1 (rerun memo crash), Bug 2 (duplicate-lookup phantom failure), and Bug 3 (watchlist reads local files) are breaking users **today**, and their "proper" fixes land in Phases 2–6. Fix them now in the current codebase as small patches; note in the spec that Phase 2's identity work *replaces* the Bug 2 patch rather than assuming it.

### F7 — Golden set (Phase 0) can't express Phase 3+ invariants yet; say so
§20.5's invariants ("which evidence is material, which criteria cannot be scored") require the claims machinery that doesn't exist until Phase 3. Phase 0's golden set v1 can only pin *current-pipeline* behavior (identity outcome, scores, recommendation, human-review flags). Version the golden set per phase and extend it as each substrate lands — otherwise Phase 0's exit criterion is quietly unmeetable.

### F8 — Frontend phasing is missing, and one UX decision is being made silently
§16 describes what is effectively a new app (evidence ledger, decision record, ambiguity queue, FI inbox) with no statement of which UI ships with which phase. Two concrete gaps: (a) Phase 2's exit criterion ("ambiguous matches do not auto-merge") creates a queue that *someone must be able to work* — the IdentityResolutionCase UI is therefore a Phase 2 deliverable, not a later nicety; (b) §16.1's "the queue does not lead with a universal numerical score" quietly reverses the current docket design (the conviction number is the row's most-iterated element). That may be the right call, but it's a product decision the GP-facing design work should make consciously — it should be listed in §23/§24 as a decision, not embedded in a bullet.

### F9 — Per-deal model cost has no baseline or target
Extraction and verification are new model passes per artifact; a 12-artifact opportunity could cost several times today's 3-persona review. §20.6's shadow mode compares cost (good), but there's no target. Add one number to §19.3: shadow-mode cost per decision-ready opportunity within N× of the current pipeline (pick N deliberately — 2× is probably acceptable for the trust gained; 6× is not).

### F10 (small, factual) — Phase 0's MetaAgent freeze is smaller than it sounds
Prompt mutation is already promotion-gated with auto-apply off by default (`meta/prompt_gating.py`, `META_AGENT_PROMPT_AUTO_APPLY=false`). What actually self-applies today is the **reweighter and calibrator** — plus the every-5-minutes over-running from audit Bug 5. Phase 0's deliverable should name those specifically, otherwise it risks "completing" by disabling something that was already off while the real auto-mutations keep running.

---

## Punch list (spec edits, in order)

1. Add the enum-mapping table + single-adapter rule (F1).
2. Add latency budgets + the interactive fast path to §9/§10 and Phase 1 exit criteria (F2).
3. Rename Phase 2 dual-write to write-new/project-legacy via outbox (F3).
4. Snapshot claim status by value in EvaluationRun (F4).
5. Add "coordinate with Postgres migration; job store on direct Postgres" to Phase 1 (F5).
6. Add a "pre-phase hotfixes" note for audit Bugs 1–3 (F6).
7. Version the golden set per phase (F7).
8. Add a UI-deliverable line per phase; move the "no leading score" queue change into §23 Decisions (F8).
9. Add a cost-multiple target to §19.3 (F9).
10. Reword Phase 0's meta deliverable to name reweighter/calibrator/interval specifically (F10).

None of these change the architecture. F1–F4 change what gets built first and how; the rest are precision fixes to a spec that is otherwise ready to drive implementation planning.

---

## Appendix — Frontend impact analysis (expands F8)

The design affects every surface, but unevenly. Because §17 keeps `/api/startups` and memo routes as compatibility projections, the frontend can migrate surface-by-surface — nothing forces a big-bang rewrite.

### The two real rebuilds

**Memo → Decision Record.** §16.2 demotes the memo to "a narrative projection within this record." The broadsheet (`InvestmentMemoContent`, ~1,275 lines + 1,645-line stylesheet) is NOT thrown away — it becomes one view inside a record whose spine is recommendation → decisive evidence → gaps/contradictions → criterion assessments → founder evidence → conditions-to-change → ruling → history. Crucially, the memo already has proto-versions of most spine sections (adverse register, focal question, AssessmentScorecard, missing-data items, ruling section, precedent strip, run log) — so this is a *re-anchoring* of existing sections from generated JSON onto authoritative records, plus two genuinely new component families: the **evidence ledger** (filterable claims with assertion-class chips — EXTERNALLY_VERIFIED / FOUNDER_ASSERTED / MODEL_INFERRED / CONFLICTED as typographic states; a broadsheet-native design task) and the **recommendation-change delta view** (§12.5), which replaces "regenerate the memo" as the update idiom. The permanent tax: old persona-shaped rows render forever, so `AssessmentScorecard` and the review sections must branch on artifact generation (persona rows vs criterion assessments).

**Dispatch internals.** `useDispatchLookup` (~630 lines) rewires from lookup_id/pipeline_state correlation to observation → opportunity → evaluation states. The UX largely survives (the resolve-preview picker already exists and becomes mandatory-before-enrichment, matching §8.2), but two states change meaning: INSUFFICIENT_EVIDENCE becomes a *terminal card state* rather than a failure, and "already in your deal flow" becomes a first-class dedup outcome instead of today's phantom error.

### The sensitive design decision

**The docket loses its leading number.** §16.1's "the queue does not lead with a universal numerical score" reverses the current row design — the conviction integer is the docket's most-iterated element (including this week's badge work). The new row leads with recommendation state + attention priority + evidence-quality warnings. This may well be right (§12.2's "a score is policy-relative" argues for it), but it's the single most user-visible change in the whole migration and should be decided as a design exploration, not inherited from a spec bullet. Mitigating good news: `queueAttentionDriver` (~500 lines of client-side heuristics inferring attention from scattered fields) mostly *dissolves* — the server's `attention_priority` and `process_state`/`decision_state` replace inference with data. The frontend gets simpler here.

### Net-new surfaces (by phase)

| Phase | New UI deliverable |
|---|---|
| 0–1 | Nearly none; optional blocked/dead-letter job visibility strip |
| 2 | **Identity resolution queue** (merge/split/confirm cases — second register in the Flow docket idiom) + source-channel attribution on rows |
| 3 | **Evidence ledger** + assertion-class treatment inside the memo; founder-evidence section |
| 4 | Decision-record spine; INSUFFICIENT_EVIDENCE states; recommendation-change delta; the queue re-lead decision |
| 5 | Ruling controls v2 (ADVANCE + optional confidence + one-click override-reason categories); diligence-question sheet; info-request draft approval |
| 6 | Service-level indicators + refresh-reason provenance ("refreshed 2d ago — monitor due") |
| 7 | **Fund Intelligence inbox** (accept/edit/reject/defer proposals) — retires most of the meta internals panels (~1,000 lines become shadow-mode diagnostics or die) |

### Mechanical (large but low-risk)

`types/startup.ts` (~690 lines) gains Company/Opportunity/Evaluation/Recommendation/Ruling/Claim types with the legacy Startup type demoted to a projection; new typed clients per §17 API group; new TanStack keys + warm-start keys; SSE grows from one `startups_changed` nudge to the outbox event vocabulary (`evaluation_completed`, `ruling_recorded`, …) — which enables *finer* invalidation and less refetch than today.

### F1 lands in the frontend too

`DecisionBadge`, `DECISION_BADGE_LABEL`, `verdictBadgeTokens`, and — critically — **user-configured `verdictBadges` in saved fund configurations are keyed by INVEST/PASS/MONITOR ids**. The INVEST→ADVANCE rename therefore touches persisted user settings data, not just labels. The enum-mapping adapter from F1 must exist client-side as well, and badge config needs a migration.

### What survives untouched

Auth shell, AppFrame/spine, design system tokens, login/warm-start machinery, the home briefing structure (digest content changes, shape doesn't), portfolio page shell (data source changes to service levels), PDF export (re-pointed at the §15.4 decision-pack projection), and Settings' room structure (§12.1's thesis/policy/rules separation matches the existing rooms; new rooms for service levels, data sources, retention slot in beside them).
