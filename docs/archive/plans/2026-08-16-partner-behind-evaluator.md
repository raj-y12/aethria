# Partner-Behind-Evaluator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `partner/decision.py` stops computing an independent recommendation. Canonical `evaluate_snapshot()` becomes the single recommendation authority; the real policy `partner/decision.py` currently owns (mandate-fit gating, ownership-conflict fail-closed check, and the risk/driver facts it derives) gets ported to a canonical home as small, reused functions — not re-implemented as a second 2,000-line engine.

**Architecture:** Ponytail lens applied throughout: reuse what already exists (`check_ownership_conflict`, `partner_rules.mandate_fit` config, canonical's own per-criterion `missing_evidence`/`contradicting_claim_ids`) instead of re-deriving it; drop machinery that only ever produced fake precision (the numeric `conviction_adjust` ladder) in favor of naming the underlying fact directly; keep the one piece that's a genuine, invariant-8-sanctioned exception (LLM escalation for truly ambiguous cases) but don't assume its current ~500 lines are all load-bearing until read in full.

**Tech Stack:** Python 3.12, Pydantic, existing `evaluation_v2` and `identity` modules. No new dependencies.

## Global Constraints

(Same as the master plan — [2026-08-16-legacy-canonical-consolidation.md](2026-08-16-legacy-canonical-consolidation.md#global-constraints).) Notably for this sub-project: no threshold hardcoded in Python (invariant 3); no silent recommendation change (invariant 5, product-safety); never weaken a test to make this pass.

---

## What was found reading `partner/decision.py` (2,210 lines) and `partner/engine.py` (794 lines) in full

Real, unique policy — no canonical equivalent, must be ported, not deleted:

| Piece | Where | Lines (approx) |
|---|---|---|
| Mandate-fit gating (strong/partial/weak/outside-thesis tiers, "held for IC exception") | `_finalize_thesis_and_mandate_gate` | ~140 |
| Ownership-conflict fail-closed check | called from the same method, via `identity.ownership_gate.check_ownership_conflict` | already a standalone reusable function |
| Portfolio-concentration conviction penalty | inline in `decide()`, ~line 1037-1043 | ~10 |
| Six risk/driver predicates (critical-risk, red-flags, contradictory-scores, missing-assumptions, missing-team, missing-business-model) | `_has_critical_risk`, `_has_red_flags`, `_has_contradictory_scores`, `_has_missing_assumptions_affecting_decision`, `_has_missing_team`, `_has_missing_business_model` | ~150 total |
| The audited hardcoded conviction | [decision.py:945](../../../backend/partner/decision.py:945) — `conviction=8` in the critical-risk-plus-incomplete-coverage branch | 1 line, real bug |
| LLM escalation for grey-zone/contradictory cases | `_decide_with_llm`, `_compact_llm_rescue_call`, `_align_llm_partner_payload`, plus JSON-budget/parsing helpers | ~500, **not yet read in full — see Task 5** |

Already redundant with canonical, safe to delete outright:
- `_canonical_recommendation` (the avg-score → INVEST/PASS/MONITOR ladder) — `evaluate_snapshot()` already produces this from claims. It already partially defers to `self.evaluation_policy` when `evaluation_prerequisites` is passed, confirming the two threshold sources were already meant to converge.

---

### Task 1: Delete the redundant threshold ladder, read from canonical instead

**Files:**
- Modify: `backend/partner/decision.py` — `_canonical_recommendation`, `_enforce_canonical_recommendation`, and every call site inside `decide()` that calls `_canonical_recommendation(avg_score)`.
- Modify: whatever caller currently passes `evaluate_snapshot()`'s result into the same code path as `decide()` (find via `grep -rn "PartnerDecisionEngine(" backend/ --include=*.py`, excluding tests, before writing this task's exact diff).
- Test: `backend/tests/partner/` — existing threshold tests must still pass with the new source.

**Interfaces:**
- Consumes: `evaluate_snapshot()`'s `EvaluationResult.recommendation` (already exists, already a `str` in `{"advance", "monitor", "pass"}`-shaped canonical vocabulary — confirm exact enum via `backend/evaluation_v2/service.py` before writing code).
- Produces: `decide()` no longer computes its own INVEST/PASS/MONITOR from `avg_score`; it takes the canonical recommendation as an input parameter instead.

**DONE — status and what was actually learned doing it:**

- [x] Confirmed `evaluate_snapshot()`'s recommendation shape: `RecommendationState` enum (`advance`/`monitor`/`pass`/`insufficient_evidence`, lowercase).
- [x] Found every call site of `_canonical_recommendation` (3) and `_enforce_canonical_recommendation` (1, itself — dead code, deleted outright, zero external callers).
- [x] **Correction found mid-implementation:** `decide()`'s `score_recommendation` variable is *not* what determines the final recommendation for the currently-active rules version. `_branch_recommendation()` (line ~1091) explicitly discards `score_recommendation` for non-v3 rules: `return score_recommendation if historical_v3 else configured` — v4 rules are verdict-authoritative, not score-authoritative, by design (see the code's own comment). Threading the canonical override into `score_recommendation` alone was silently ineffective, caught by the tests written for this task (`test_canonical_pass_overrides_a_high_score_that_would_otherwise_invest` failed with the override producing no change). Fixed by intercepting at `_emit_deterministic()` instead — the actual single choke point every deterministic verdict branch (STRONG/MEDIUM/WEAK, v3's ladder) calls through — applying the canonical override there, gated on `not has_critical_risk` so the fail-closed critical-risk PASS is never second-guessed.
- [x] `canonical_recommendation` threaded as an optional parameter through `decide_with_execution_identity()` → `decide()` → `partner/engine.py::_decide_and_save()` → `run_startup()`.
- [x] **Sequencing fix (not in the original task list, discovered necessary):** `partner_engine.run_startup()` is called from `pipeline_runner.py` *before* any canonical evaluation existed for that dispatch — the canonical `evaluate()` bridge ran only at the very end, in `jobs/handlers.py`, after Partner had already run. Moved the `EvaluationRepository.evaluate()` call from `jobs/handlers.py` to `pipeline_runner.py::_run_on_demand_lookup_inner`, right after canonical identity admission (claims already persisted there) and before Reviewer runs. The late call in `jobs/handlers.py` was removed to avoid double-evaluating.
- [x] Left the two "insufficient evidence coverage" branches (avg_dims < required_dimensions, lines ~936-1013) untouched — they're this engine's own fail-closed detection and don't call `_emit_deterministic`; overriding them with canonical's opinion would be a scope-creeping, weaker-safety change, not this task's job.
- [x] The periodic pipeline cycle (`run_one_pipeline_cycle` → `partner_engine.run_cycle`) is **not** bridged to canonical evaluation — `canonical_recommendation` defaults to `None` there, so it falls back to the pre-existing verdict-ladder behavior, unchanged. Bridging the periodic cycle is explicitly out of scope for this task.
- [x] `backend/tests/test_partner_canonical_recommendation.py` (new, 5 tests) covers: canonical override in both directions, `insufficient_evidence` correctly not forced onto the ladder, no-canonical fallback matches pre-existing behavior, and critical-risk still wins over a canonical "advance."
- [x] Full backend suite: 2186 passed (3 pre-existing Postgres-container-only failures, unrelated), 0 regressions.
- [ ] Commit — not yet done, pending user confirmation.

---

### Task 2: Fix the audited hardcoded conviction, extract to config

**Files:**
- Modify: `backend/partner/decision.py:945` (the `conviction=8` literal).
- Modify: `resources/config/partner_rules/` — add the threshold to whichever version file is currently active (check `resources/config/active.json` first).
- Test: `backend/tests/evaluation_v2/test_partner_rules_contract.py` — extend to cover the new field.

**Interfaces:**
- Consumes: `rules.<new_field>` from the loaded `PartnerRules` object (same pattern as every other threshold in this file, e.g. `rules.score_thresholds.min_avg_pass`).
- Produces: no behavior change — same conviction value, now sourced from versioned policy instead of a Python literal.

**DONE — status and what was actually decided:**

- [x] Added `critical_risk_pass_conviction: Conviction` to the shared base `PartnerRules` model (not V4-only) — `test_partner_rules_contract.py`'s contract tests are anchored to `v3.json` specifically, so a V4-only field would have broken v3 parsing.
- [x] **No version bump.** Added the field directly to `v3.json` and `v4.json` with the same value (`8`) that was already hardcoded — this doesn't change either version's *behavior* (identical outcome, same value, just now explicit data instead of a Python literal), which is a different thing from the "never mutate a published version's meaning" rule that's meant to stop silent threshold changes. A version bump would have been the safer default for an actual value change; this wasn't one.
- [x] Replaced `conviction=8` with `rules.critical_risk_pass_conviction` at the exact line the audit flagged.
- [x] Registered the new leaf in `test_partner_rules_v4_authority.py`'s `_CONSUMER_GROUPS` (under `critical_risk_clamp`, alongside the sibling `critical_risk_keywords`) — the mutation-coverage test enumerates every leaf in `v4.json` and fails if one isn't registered; this one wasn't, caught immediately.
- [x] `test_partner_rules_contract.py` needed no changes — its leaf-path list is auto-derived from `v3.json`, so it picked up the new field on its own.
- [x] New test: `backend/tests/test_partner_critical_risk_conviction.py` — parses `v4.json`, mutates the field to a different value, confirms `decide()`'s output conviction actually reflects it (not silently reading a cached/hardcoded value).
- [x] Full backend suite: 2191 passed, 0 regressions (3 pre-existing Postgres-container-only failures, unrelated).
- [ ] Commit — pending user confirmation.

---

### Task 3: Port mandate-fit gating and ownership-conflict as a canonical post-processing gate

**BLOCKED — reordered after Sub-project 4, not attempted yet.** Read `identity/ownership_gate.py::check_ownership_conflict` in full: it's a small, self-contained regex match over **narrative text** (`scout_output`/`review_output` prose — "acquired by", "now a subsidiary of", etc.), not canonical claims. Same story for `thesis_alignment_score`/`thesis_alignment_confidence`, read off `review_output` — also legacy narrative, not a canonical claim. Canonical `evaluate_snapshot()` only ever sees typed claims; it has no equivalent of "read the reviewer's narrative summary for acquisition language" and no thesis-alignment input at all today.

This means Task 3 cannot actually move to canonical until Sub-project 4 (canonical evidence extraction) gives canonical evaluation some way to see narrative-derived signals — the dependency runs the opposite direction from how the master plan originally sequenced it (4 was assumed to come after 1–3; it turns out 3 needs a slice of 4 first). Decided to skip to Task 5 now and revisit Task 3 once Sub-project 4 exists, rather than building a narrow one-off slice of evidence extraction just to unblock this, or leaving the logic in place and calling it done despite the task title.

**When revisited:** the original plan below is still the right shape once the input problem is solved — reuse `check_ownership_conflict` as-is (it needs no changes, just a canonical caller with access to the narrative text), reuse `partner_rules.mandate_fit`'s existing thresholds, land it as one small pure function, not a new class.

- [ ] Re-read `_finalize_thesis_and_mandate_gate` in full (already read once this session, [decision.py:603-738](../../../backend/partner/decision.py:603)).
- [ ] Determine where `thesis_alignment_score` and `thesis_alignment_confidence` come from on the canonical side once Sub-project 4 exists.
- [ ] Write `apply_mandate_gate(recommendation, thesis_alignment_score, thesis_alignment_confidence, ownership_conflict) -> GatedRecommendation` as one small pure function in `evaluation_v2/`. Reuse `check_ownership_conflict` directly; do not reimplement it.
- [ ] The four fit-tier thresholds already live in versioned `partner_rules.mandate_fit` — reuse as-is.
- [ ] Required test: golden-set comparison — for a fixed set of (recommendation, thesis_alignment, ownership_conflict) inputs, the new gate produces the same gate/held/override outcome as `_finalize_thesis_and_mandate_gate` did.

---

### Task 4: Replace the numeric conviction adjustments with named facts

**DONE — but the real scope turned out much narrower than planned, and stayed legacy-side rather than porting to canonical.**

Re-reading `decide()` against `partner/rationale.py` found that **4 of the 6 predicates were already named**, just not the way the plan assumed: `derive_situation_tags()` already turns `has_critical_risk`, `has_contradiction`, `reviewer_disagreement`, and `has_missing_critical_qualitative` (team-or-business-model) into tags that feed both `decision_drivers` and the rationale prose. Only two things ever adjusted `conviction_adjust` with **no** named trace anywhere: `_has_red_flags` (only flipped `human_review_required`) and `_has_missing_assumptions_affecting_decision` (only an LLM-trigger condition). Portfolio-concentration was a mixed case — the sector-saturation penalty (≥3 in one sector) already got a prose sentence via `sector_concentration_note`, but no driver tag; the large-portfolio/Pre-Seed penalty had no surfacing of any kind, the most silent of all of them.

**Did not port to canonical** — same blocker as Task 3, discovered the same way: canonical `evaluate_snapshot()` has no equivalent of `derive_situation_tags`/`compose_decision_rationale`, and weaving new tags into that existing, tested `TAG_PRIORITY` system risked shifting which tag wins as `primary` for scenarios that don't involve these facts at all — a bigger blast radius than the fix needed. Instead: additive, surgical fix, entirely inside `partner/decision.py`, still legacy-side. These fields (`decision_drivers`, `conviction_level`) are genuinely still user-facing today outside the redesigned memo sections — confirmed the Queue/Flow listing, IC-pack export, and attention-driver logic all still read legacy `startup.partner.*` fields, so this isn't dead code being polished for nothing.

- [x] Named the two genuinely-silent predicates (`red_flag_language_in_key_risks`, `unresolved_assumption_risk`) and both portfolio-concentration conditions (`portfolio_sector_concentration`, `large_portfolio_pre_seed_caution`) as plain strings in a `silent_conviction_facts` list, computed once alongside the existing `conviction_adjust` logic.
- [x] Appended `silent_conviction_facts` onto `result["decision_drivers"]` at both places a final `decision_drivers` list gets set — `_emit_deterministic` (the deterministic path) and `_align_llm_partner_payload` (the LLM-escalation path, threaded through as a new optional parameter since it's a plain method, not a closure).
- [x] Additive only — the existing `sector_concentration_note` prose sentence and the `conviction_adjust` numeric delta are both untouched; this only adds visibility, doesn't remove or replace anything (avoids an actual behavior/value change under invariant 5).
- [x] New test file `test_partner_silent_conviction_facts.py` — 3 tests, one per newly-named fact category (red-flag keyword, large-Pre-Seed-portfolio, sector concentration), using a fake `portfolio_store` matching `_get_portfolio_context()`'s real read pattern. (`unresolved_assumption_risk` shares the identical append mechanism already covered by the other three — not given its own test, diminishing marginal value.)
- [x] Full backend suite: 2195 passed, 0 regressions.

---

### Task 5: Read and scope the LLM-escalation path

**DONE — read in full, and found a real gap that's now fixed rather than just scoped.**

- [x] Read `_decide_with_llm`, `_compact_llm_rescue_call`, `_align_llm_partner_payload` in full. Key finding: **the LLM never decides the recommendation.** Its own docstring: *"Canonical recommendation is fixed by the caller; model supplies defense narrative only."* `final_recommendation` is always a caller-supplied parameter — the LLM only writes rationale/confidence text defending a recommendation the deterministic rules already picked. This means the "escalation" is materially smaller than the ~500 lines suggested: no separate decision authority to reconcile with canonical, just a narrative generator.
- [x] Checked `_json_within_budget`/`_partner_rules_json_for_prompt` against `utils/` — no existing duplicate. Genuinely partner-specific, not bloat.
- [x] **Found and fixed a real gap**, not just scoped one: all 3 call sites that trigger `_decide_with_llm` (low-score-near-threshold edge case, MEDIUM-verdict grey zone, MEDIUM borderline band) compute `final_recommendation` from raw `score_recommendation`/`branch_recommendation` — bypassing `_emit_deterministic()` entirely, so Task 1's canonical override never reached them. Two *other* usages of the same variables do go through `_emit_deterministic` and were already covered.
- [x] Extracted the override into a shared `_canonical_override_or()` helper (used by `_emit_deterministic` too, replacing its inline duplicate of the same check) and applied it at all 3 LLM-trigger call sites, so a canonical recommendation now overrides the LLM path's fixed recommendation exactly like the deterministic path.
- [x] New test: `test_canonical_override_also_reaches_the_grey_zone_llm_escalation_path` in `test_partner_canonical_recommendation.py` — stubs `_decide_with_llm` (same pattern as the existing `test_medium_6_4_borderline_routes_to_llm`), confirms the canonical value reaches the escalation call, not the raw score-ladder value.
- [x] Full backend suite: 2192 passed, 0 regressions.
- No canonical port of the retry/rescue machinery itself needed — it's narrative-only, so there's nothing decision-bearing left to reconcile.

---

### Task 6: Cut over, verify, delete

**Files:**
- Modify: every caller of `PartnerDecisionEngine`/`PartnerEngine.run_startup` found in Task 1 — repoint to the canonical-gated path.
- Delete: `partner/decision.py`'s now-empty scaffolding, once Tasks 1-5 have moved every real behavior out. Do not delete the file itself until this is confirmed — it may still own the compatibility-projection write to `startup.partner_info` that legacy API consumers need (check API.md for what's still contractually promised there before deleting the writer).

**Acceptance criteria (matches the master plan):**
- A dispatch produces exactly one recommendation.
- No API response field is silently renamed or removed (API.md updated in the same change if anything does change).
- Golden-set comparison (old vs. new, same evidence in) shows equivalence or an explicitly-reviewed, deliberate difference — never a silent one.
- Full gate passes: `python3 -m pytest -o asyncio_mode=auto` and the frontend gate.

- [ ] Run the golden-set comparison across all five tasks' changes together, not just per-task.
- [ ] Confirm nothing still imports the deleted pieces (`grep -rn "_canonical_recommendation\|_finalize_thesis_and_mandate_gate" backend/ --include=*.py`).
- [ ] Update API.md if any response shape changed.
- [ ] Run the full verification gate.
- [ ] Commit.
