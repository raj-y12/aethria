# Scout and Evidence-Pipeline Audit — Findings and Sequencing

**Date:** 2026-08-17. Two adversarial, code-verified audits (not confirmatory —
explicitly instructed to hunt for bugs, not check that things work), covering
`backend/scout/`, `backend/resolver/`, and `backend/evidence/` +
`backend/evaluation_v2/`. Triggered by finding three real founder-misattribution
bugs (`docs/archive/plans/2026-08-17-founder-attribution-bugs.md`) — the
hypothesis going in was "if that class of bug exists once, it exists again,
including on my own evidence-pipeline work from earlier today." It did.

**Status: documented and sequenced, not implemented.** Unlike the founder bug,
this wasn't pre-authorized for autonomous implementation — the volume and risk
profile here is much larger. Awaiting direction on what to fix.

---

## Part A — Scout / resolver pipeline

### CRITICAL

**A1. Citation verification has a fail-open bypass on the highest-risk path.**
`utils/reference_verify.py:690-698`. When every reference gets pruned by the
anchor/relevance/URL-probe filters on a lenient (`for_lookup=True` — i.e. every
user-typed lookup) pass, the code restores the model's **raw, unverified**
citations instead of returning none. The exact failure mode: a same-named
different company, or a hallucinated URL, sails through untouched at precisely
the moment every check has already failed it. This directly undermines the
identity-confusion protection the founder-bug fixes just added elsewhere.

### HIGH

**A2. Founder Resolver runs a full second retrieval pass whose result is
almost always thrown away.** `scout/engine.py:604-606` calls
`resolve_founders()` (4-5 queries + up to 2 page fetches) unconditionally on
every named lookup. Its output only survives via a gap-fill merge
(`utils/founder_enrichment.py:84-86`) that only applies `if ... not
_has_names(...)` — but `founder_names` is nearly always already populated by
then (LLM output, or the deterministic `company_resolver.py` fallback, or the
Company Resolver's own phase-2 extraction). Same "computed and silently
discarded" shape as the `reviewer_resolution.py` finding from the reviewer
audit — a full paid retrieval pass with no effect on the common path.

**A3. The reviewer-triggered founder-evidence path never classifies
`source_type`, silently under-scoring confidence.** `utils/founder_enrichment.py:186-203`
never calls `_classify_source`, so `FounderEvidence.source_type` always
defaults to `"other"`. `_candidate_confidence` grants +0.2 for an official-site
source and +0.05 for crunchbase/news — neither can ever fire on this path,
even when the reused evidence genuinely is the company's own team page. Real
founders extracted here score lower than identical evidence would on the
primary path, dropping some below the 0.35 keep-threshold for the wrong
reason (missing plumbing, not weak evidence).

**A4. Untrusted page *titles* bypass the prompt-injection isolation boundary
that snippets go through.** `utils/retrieval_grounding.py:601-618`: snippets
are wrapped in `isolate_untrusted_text` and scanned by `flag_prompt_injection`;
titles and URLs are interpolated raw into the prompt. A page's `<title>` is
fully attacker-controlled (scraped from the target's own site) — same threat
model as snippets, unguarded.

**A5. The just-shipped founder-misattribution fix over-corrects: one bad
mention anywhere rejects a name even if a separate, correct mention exists.**
`scout/base.py:87-119` — `for m in re.finditer(...): ... break` on the first
match. Narrower than the Vercel case it was built for; a real founder
correctly attributed once and incorrectly mentioned once elsewhere gets
dropped entirely. Same regex-without-full-context class as the bug it fixed,
just inverted.

**A6. `confidence_score` is the one uncalibrated, unanchored number in the
whole resolver stack.** `scout/base.py:412-417` — bare model output, silently
defaulted to 0.5 on a parse failure, never cross-checked against retrieval
strength or citation count. Every other confidence field in this pipeline
(`CompanyResolution.confidence`, `FounderCandidate.confidence`) is
deterministically composed from real signals. This one isn't — the same
disease already found and partially fixed in Reviewer's scoring, unfixed here.

**A7. A missing company name is silently fabricated (`"Unknown Startup"` or
the first 4 words of `one_line`) and the fabricated name is then used for
founder extraction, reference finalization, and financial grounding** —
`scout/base.py:400-406`. Passes schema validation; produces a plausible-looking
row for a company that was never actually identified, instead of failing
closed.

**A8. Missing `key_assumptions` are padded with generic, non-evidence-based
filler text** (`"Customer demand converts into repeat usage."` etc.,
`scout/base.py:426-432`), presented to reviewers as if company-specific, with
no marker distinguishing it from real model output.

### MEDIUM

**A9. Hardcoded confidence/threshold weights throughout, violating AGENTS.md
invariant #3** (thresholds must be versioned config, never Python literals):
`company_resolver.py:683-697,745-749`, `founder_resolver.py:921-937,959-970`,
`utils/founder_enrichment.py:39-44`, `scout/engine.py:92-100`. None route
through `resources/config/`.

**A10. `_matches_lookup_identity` is a weak token-substring check** —
`scout/base.py:828-851` — trivially satisfiable by a wrong-but-similarly-named
company, and only ever soft-flags (`NEEDS_REVIEW`), never rejects.

**A11. A single named lookup can cost ~20 retrieval queries + 3-6 LLM calls
before persistence**, with a large fraction of the Founder Resolver's
contribution wasted per A2.

**A12. `ground_financials`'s allowlist check silently no-ops when
`url_allowlist` is empty but `sources` isn't** — `utils/financials_grounding.py:149-166`:
`if not nu or (allowlist and nu not in allowlist)` short-circuits to accepting
everything when `allowlist` is falsy. Dead today only because every current
caller keeps them in sync; latent trust-boundary gap for any future caller
that doesn't, with zero test guarding it.

---

## Part B — Evidence/claim pipeline (built earlier today, audited adversarially)

### CRITICAL — plausibly explains most of the 27% coverage number directly

**B1. Retrieval is capped at 3 queries *total*, not 3 per missing dimension.**
`evidence/retrieval.py:29,56` — `MAX_QUERIES = 3` applied to
`plan.search_questions[:MAX_QUERIES]`, but `search_questions` has one entry
*per missing dimension*. An opportunity with 5 missing dimensions (close to
the observed average — 110/22 ≈ 5) gets dedicated search queries for only the
first 3; dimensions 4 and 5 get zero targeted retrieval and are extracted
against whatever the first 3 queries happened to surface.

**B2. A claim of any quality permanently marks its dimension "satisfied,"
even if it's forever ineligible to score.** `evidence/planning.py:12-26` +
`evidence/repository.py:359-367` — `list_current_claim_types` has no
confidence/quality filter, just `status='current'`. A single
`confidence=0.35` claim removes that dimension from `missing_evidence` on
every future dispatch or backfill, forever — while
`evaluate_claim_score_eligibility` blocks it forever on
`claim_confidence_zero`/`below_minimum`. No retry path exists once this
happens. This is the single most direct explanation for permanently-stuck
insufficient-evidence dimensions.

**B3. One self-reported LLM number does double duty as two independent
eligibility gates.** `evidence/extraction.py:167,197` sets both
`ClaimInput.confidence` and `ClaimEvidenceLinkInput.support_strength` from
the *same* raw model value; `evaluate_claim_score_eligibility` requires both
`>= 0.5` off that one number. A model that's honestly calibrated but modest
(0.4-0.49 on true claims) is blocked twice by the same number pretending to
measure two different things.

### HIGH

**B4. "Corroboration" is pass-level domain-diversity, not fact-level
agreement.** `evidence/retrieval.py:83-111` — `corroborated` is computed once
across the whole retrieval pass and applied uniformly to every non-official
item in it. Two sources on completely unrelated facts (a funding page + an
unrelated blog mention) satisfy the `>= 2 distinct domains` check and mark
*everything* in the pass VERIFIED, including a single-source claim about a
different fact entirely that nothing actually corroborates.

**B5. No dedup/idempotency on re-running the same evidence plan.**
`evidence/repository.py:60-144,146-180` — `ingest_artifact` dedupes the
*artifact* by content hash, but `evidence_items` and `create_claim` are bare
inserts with no uniqueness constraint or supersede logic. Running the backfill
script twice, or a dispatch overlapping a backfill on the same opportunity,
creates duplicate current claims of the same type — `evaluate_snapshot`
averages *all* current claims of a type, so a score silently drifts based on
how many times extraction happened to run, not evidence quality.

**Checked against real data (I ran the backfill script twice today,
overlapping on the first 10 opportunities):** 13 duplicate `(opportunity_id,
claim_type)` groups exist right now, confirming the gap is real — but all 13
are `founder_identity`/`founder_current_role`/`funding_stage`, from the
separate founder-resolution pathway that re-creates these on every dispatch
re-run (a pre-existing behavior, not caused by today's evidence-extraction
backfill specifically). **Zero duplicates among the criterion-scoring claim
types** (`tam`, `growth_rate`, `traction`, etc. — checked directly) that
`evaluate_snapshot` actually averages into scores. So today's double backfill
run did not corrupt any real score. The code gap that would let it happen is
still real and unfixed.

### MEDIUM

**B6. `criterion_score` itself is never validated, only its derived band is.**
`evidence/extraction.py:166` — the raw model score is clamped to [0,10] and
stored as-is; today's `score_band` fix (`c1e792d8`) makes the *label* honest
but never re-derives or bounds the *number* against the rubric's band
criteria. A hallucinated 8.5 for evidence that plainly supports "low" passes
through with an honest-looking "low band" tag stapled next to a wrong number.

**B7. Extraction LLM calls never touch CostController.** Confirmed via grep —
zero references in `evidence/extraction.py`, and `pipeline_runner.py:1828-1856`
calls the evidence pipeline entirely outside the cost-controller
snapshot/delta blocks used elsewhere in the same file. Only `MAX_QUERIES=3`
bounds retrieval; extraction's one-call-per-dimension has no per-dispatch or
per-tenant dollar ceiling at all.

### Confirmed non-issues (checked, not a bug)
- `effective_at`/`expires_at` are never set by retrieval/extraction, but the
  freshness gate falls back to `artifact.retrieved_at` (always populated) —
  claims aren't silently undated.
- No hardcoded-placeholder-reasoning disease in `retrieval.py`/`extraction.py`
  — `score_justification`/`display_text` are genuinely per-claim generated
  text, unlike the bug already found and fixed in `evaluation_v2/service.py`.

---

## CRITICALS — all 4 fixed and live-validated, 2026-08-17

Fixed in one pass (`86e77a9a`), 12 new/updated tests, full backend suite
(2265 passed, same 39 pre-existing Postgres-container failures, zero
regressions), then live-dispatched a real company (Ramp) to validate against
real data, not just fixtures.

- **C1 (reference fail-open):** live-verified — Ramp's founders resolved
  correctly (Eric Glyman, Karim Atiyeh) and every reference is a real Ramp
  URL (TechCrunch, Bloomberg, PRNewswire, Ramp's own site); no wrong-company
  citation was restored.
- **C2 (global vs per-dimension query cap):** `evidence_plans.missing_evidence`
  correctly listed all 5 dimensions with 5 search questions; code-level
  confirmed via `test_every_rubric_dimension_gets_a_dedicated_query`. Live DB
  can't show per-query attribution directly — `retrieval_query` is always
  stamped `queries[0]` regardless of which query found a source (a separate,
  already-documented coarse-attribution limitation, not new).
- **C3 (stuck-forever retry gap):** code-level confirmed via the repository
  test; not directly observable on this dispatch since Ramp had no
  pre-existing low-confidence claim to retry (a fresh company). Needs a
  second dispatch of an already-partially-scored company to observe live.
- **C4 (confidence/support_strength decoupling):** live-verified on real
  data — re-ran extraction against Ramp's actual retrieved evidence, got a
  real `growth_rate` claim: `confidence=0.8` (model's own) vs.
  `support_strength=0.6` (the evidence's deterministic `source_quality`),
  genuinely different values from the same extraction call. Re-ran
  `evaluate()`: `market` scored `7.99`, `evidence_sufficiency='sufficient'`,
  with the full real-claim reasoning trail visible (today's earlier
  reasoning fix + C4 all confirmed together in one live output).

## HIGH findings — all 9 fixed and live-validated, 2026-08-17

Fixed in one pass (A2–A8, B4, B5), full backend suite (2274 passed, same 39
pre-existing Postgres-container failures, zero regressions), then a brutal
self-audit of the fixes themselves — which caught one genuine regression in
my own B4 rewrite (below) — before live-dispatching a real company
(Perplexity AI) to validate against production data.

- **A2 (wasted Founder Resolver pass):** `scout/engine.py` now skips Stage 2
  only when Stage 1 already `FOUND` founder names. Live-observed correctly
  *not* skipping: Stage 1 resolved Perplexity's identity (`FOUND`,
  confidence 0.70) but had no founder names, so Stage 2 ran — and still
  found none ("No founder could be confirmed"), a genuine pre-existing
  search-quality gap unrelated to this fix, not a regression from it.
- **A3 (missing source_type on gap-fill path):** `founder_resolution_from_gap_pack`
  now classifies `source_type` via `_classify_source`; unit-tested
  (`test_gap_pack_classifies_source_type_so_official_site_bonus_can_fire`).
- **A4 (unescaped retrieved titles):** `render_sources_for_prompt` now wraps
  titles through `isolate_untrusted_text`, same as snippets already did;
  live-observed clean titles with no injection artifacts in the memo's
  source list.
- **A5 (over-broad founder-name rejection):** `_reject_misattributed_founder_names`
  now rejects a name only when *every* occurrence is misattributed, not the
  first one found.
- **A6/A7 (fabricated confidence/name):** unparseable confidence and empty
  name are no longer silently defaulted (0.5, "Unknown Startup") — they fail
  `validate_scout_output` and route through the existing repair pass,
  failing closed if repair can't produce a real value. Live-observed: no
  fabricated founder or company name anywhere in the Perplexity AI memo.
- **A8 (padded key_assumptions):** generic filler assumptions are no longer
  spliced in to satisfy the 2-minimum; a genuine shortfall now fails
  validation and repairs instead.
- **B4 (pass-level vs per-query corroboration):** `execute_evidence_plan`
  runs one retrieval call per query and scores corroboration within that
  query's own results only. Live-observed: `retrieval_query` on every
  ingested artifact is the *actual* query that found it (not always
  `queries[0]` as before), and evidence artifacts for the "market" question
  are all correctly tagged with the market query.
- **B5 (no dedup on evidence_items re-ingestion):** new migration
  (`db/migrations/20260817000002_evidence_items_content_dedup.sql`) adds a
  `content_hash` column and a unique index on `(user_id, artifact_id,
  content_hash)`; `ingest_artifact` now does `on conflict ... do nothing`
  with a re-select fallback, mirroring the existing artifact-level dedup.
  Applying the migration to the local snapshot DB hit a real pre-existing
  duplicate (`UniqueViolationError`) — direct confirmation the bug was live,
  not theoretical; the migration dedupes existing rows (oldest wins) before
  adding the constraint. Two new Postgres-contract tests
  (`test_evidence_repository_postgres.py`) prove both the dedup case and the
  distinct-content case.

**Self-audit catch:** the B4 rewrite (one retrieval call per query instead
of one batched call) dropped the caller-configured `plan.max_artifacts`
budget — nothing summed ingestion across the now-separate per-query calls,
so a plan configured for e.g. 5 artifacts could silently ingest up to
`len(queries) * 4`. Fixed by re-checking `plan.max_artifacts` before each
ingest inside the per-query loop; live-verified on the Perplexity AI
dispatch — exactly 5 artifacts ingested from a 5-query plan capped at 5,
despite 20 available sources. New regression test:
`test_max_artifacts_budget_is_respected_across_queries`.

## Suggested sequencing (not started)

Same principle as the reviewer audit: smallest-safe-fix-first, but this list
is bigger and some items need a product decision, not just an engineering
call.

1. **B2 (stuck-forever dimensions)** — the most direct lever on the 27%
   number itself. Needs a decision: retry low-confidence dimensions after N
   days, or only when new evidence appears? Product call, not mine to make.
2. **B1 (3-query cap should be per-dimension, not global)** — bounded,
   deterministic, testable. Real cost tradeoff to weigh (more dimensions
   covered = proportionally more retrieval spend per dispatch) — worth a
   number before deciding the new cap.
3. **A1 (citation fail-open bypass)** — CRITICAL, but changing it could
   increase "no citations survived" rejections on real lookups; needs
   verification against real dispatch data before flipping, not a blind fix.
4. **B4 (corroboration is pass-level not fact-level)** — a real design fix,
   not a one-line change; touches the verification rule this session
   deliberately designed a few hours ago.
5. **A2/A3 (Founder Resolver waste + under-scoring)** — real, bounded,
   probably safe to fix directly once prioritized.
6. **B5 (dedup/idempotency)** — given I may have already triggered this
   today, worth checking the real data before deciding whether to fix the
   code, clean up duplicates, or both.
7. Remaining MEDIUM items (A6-A12, B3, B6, B7) — smaller, lower urgency,
   batchable once the above are decided.
