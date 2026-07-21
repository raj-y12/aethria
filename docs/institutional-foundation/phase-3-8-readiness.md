# Phase 3–8 institutional domain readiness

Date: 2026-07-20

## Outcome

The code-level evidence-and-decision platform is implemented through Phase 8, including the final decision-safety remediation. It is deliberately **not certified for production in this local workspace** because no `DATABASE_URL`, `SUPABASE_DB_URL`, or `TEST_DATABASE_URL` is configured. The migrations, immutable database triggers, RLS, transaction races, and service-role permissions therefore have not been exercised against the target PostgreSQL instance. The separate authority-control cutover slice is also still pending and must not be represented as certified by these results.

The product authority model is now explicit: agents discover, extract, evaluate, recommend, draft, monitor, and propose; authenticated people rule, approve external actions, correct evidence, resolve identity, accept policy proposals, and publish policy.

## Post-interruption stabilization (2026-07-21)

The Codex run was cut off by its weekly limit mid-implementation of the
`EvaluationPrerequisites.dependency_identity` / scoring-runtime binding. That
in-progress work was left uncommitted in the worktree and is now preserved
verbatim in commit `241af513` (a WIP checkpoint, **not** a finished unit).

At the point of interruption the committed HEAD had one regressed test,
`test_production_legacy_loader_binds_exact_published_fund_config`, which
asserted object identity (`is`) against the validated/normalized bundle the
prerequisite loader now returns. Fixed in `c193df6e` (identity → value
equality). Re-verified backend only:

```bash
cd backend && pytest -q
# 1,213 passed, 10 skipped, 1 warning
```

**Not re-verified in this stabilization pass** (the 2026-07-20 figures below
predate the interruption and have not been re-measured): frontend vitest,
lint, production build, golden set v7, and the decision-safety certification
suite. Re-run those before trusting the "all green" record.

## Implemented behavior

### Evidence and founder assessment

- Artifacts, evidence items, claims, claim/evidence links, plans, and corrections are separate tenant-scoped records.
- Material externally verified claims require evidence links.
- Unsupported model-generated personality labels such as “magnetic founder” are rejected. Subjective interview observations require operator attribution.
- Restricted storage references are not exposed by the ledger API. Deck/email intake registers confidential, untrusted artifact metadata with explicit retention policy.
- Prompt-injection indicators are recorded on untrusted artifacts; document content cannot select providers, policies, recipients, or budgets.

### Evaluation and recommendation

- Evaluation runs snapshot claims and relationships under deterministic hashes and records policy, rubric, partner-rule, model, and prompt dependencies.
- Governed Reviewer and Partner runs require one tenant-bound, complete structured-scoring trace with the exact published policy version and hash; environment flags cannot disable that path.
- Published policy identity covers the normalized dimensions, decision thresholds, and score bands actually consumed. The immutable manifest records the already-consumed dependency identity without reloading mutable settings or global rules.
- Governed score precision remains lossless through review aggregation, persistence adapters, and Partner boundaries, including immediately around pass and advance thresholds.
- The active v3 Partner policy is compiled once into an immutable, extra-forbid typed contract; missing, malformed, unknown, or inconsistent decision fields fail closed rather than activating Python defaults.
- Criterion assessments and recommendations are immutable after completion.
- Missing evidence produces an unscored criterion, confidence reduction, review requirement, or diligence gap—not an invented neutral fact.
- A failed refresh appends a failure and leaves the last successful recommendation current.

### Human ruling and workflow

- Recommendations are system advice. Append-only human rulings are the authoritative fund decision.
- Overrides carry structured attribution; not every override is labeled a model failure.
- Diligence questions and information requests are generated from explicit missing evidence.
- CRM export and other external actions remain approval-gated; approval records do not falsely claim that an external write occurred.

### Monitoring and cost

- Service levels 0–5 control enrichment attention. Archive level 0 cannot refresh automatically.
- Every refresh carries a lifecycle reason, provider/resource/deadline envelope, and tenant cost reservation.
- Scheduled refresh compares a clock-independent digest over the same enriched claim/evidence projection used by evaluation before creating deeper work. The immutable, clocked evaluation snapshot hash remains separate.
- Downgrading service level releases reservations and cancels still-queued refresh jobs.

### Fund Intelligence

- Overrides become attributed learning signals and sample-disclosed proposal patterns.
- Minimum samples and preview bounds are tenant settings rather than scattered code thresholds.
- Proposals disclose evidence, attribution, sample period, confidence, and limitations.
- Accept/Edit/Reject/Defer is recorded. Acceptance creates only a draft governed policy version.
- Policy publication is a separate authenticated call through the existing compiler.
- Legacy Scout reweighting and threshold-calibration `apply` paths now fail closed as proposal-only.

### Channels and outcomes

- CSV, CRM-export CSV, event CSV, and referral CSV are bounded to 500 rows/1 MB and pass through `SourceObservation` plus canonical `IdentityService`.
- Raw unrelated CSV columns are not retained. Domains become verified identity only when the operator explicitly confirms the mapping.
- Import rows resolve, enter identity review, or record safe error codes without duplicating the company record by name.
- Outcome observations are append-only, dated, materiality-rated, and evidence-linked when marked verified.
- Outcome coverage includes positive and negative valence counts and always states that causal inference is unsupported.

## Migration order

Apply the prior Phase 0–2 chain first, then:

1. `20260715230000_evidence_claim_ledger.sql`
2. `20260715240000_immutable_evaluations.sql`
3. `20260715250000_rulings_and_actions.sql`
4. `20260715260000_attention_enrichment.sql`
5. `20260715270000_fund_intelligence.sql`
6. `20260715280000_channels_outcomes.sql`
7. `20260720120000_materiality_digests.sql`

Do not expose the new UI before all seven migrations and Phase 0–2 dependencies are applied. The repositories intentionally fail closed when their direct PostgreSQL store is unavailable.

## Verification commands

From the repository root:

```bash
cd backend
python3 scripts/run_golden_set.py --version v7 --json
python3 scripts/check_phase8_readiness.py --json
```

With `TEST_DATABASE_URL` configured, run the PostgreSQL-gated suites as part of the full backend test run. The readiness command must report all institutional tables with RLS, all immutability triggers, all migrations, no proposal activation column, and the v7 golden set passing.

## Current local evidence

- Golden set v7: 27 passed, 0 failed.
- Required second final-review focused suite: 521 passed, 0 skipped.
- Full backend suite: 1,193 passed, 10 skipped, 1 warning.
- Decision-safety certification: all 18 cases ran and passed; no certification case was skipped.
- Frontend: 58 test files and 271 tests passed; lint and production build passed.
- Readiness code checks: golden set, migration presence, and proposal-only Meta mutation paths passed.
- Direct database readiness: blocked by missing DSN (`ready: false`, expected in this workspace).
- Target migration application, RLS enforcement, UUID/JSON codecs, triggers, foreign keys, and transactional race behavior: not certified locally.
- Authority-control implementation and certification: pending as a separate slice.

## Task 8 decision-safety certification (2026-07-20)

The executable certification is
`backend/tests/evaluation_v2/test_decision_safety_certification.py`. It invokes
the real canonical evaluator, human-override classifier, and compatibility
projection with immutable local claim and evidence-relationship metadata. It
does not import legacy startup snapshots or mock the behavior being certified.

The 18 passing cases certify that:

- ungrounded high scores, model-inferred high scores, and a missing required
  dimension produce `insufficient_evidence`;
- grounded high scores combined with either a critical risk or a mandate
  exclusion produce `pass`;
- complete grounded high scores produce `advance`;
- zero and below-minimum claim confidence are ineligible, the minimum boundary
  cannot advance, and high-confidence claims can advance;
- only exact boolean `true` activates a decisive risk; exact `false` and
  malformed values do not silently activate one;
- expired and undated evidence are ineligible, while stale and lower-quality
  evidence cap an otherwise high recommendation at `monitor`;
- an `advance` recommendation followed by an `invest` human ruling is not an
  override; and
- an `advance` human ruling projects to legacy `MAYBE` with compatibility
  reason `advance`, never legacy `YES`.

The certification policy is compiled from the active
`resources/config/partner_rules/v3.json` contract, so its version, thresholds,
boundary semantics, eligibility rules, confidence caps, freshness behavior,
and decisive claim lists are the same versioned inputs exercised by the test.

Observed on 2026-07-20 from this worktree:

```bash
cd backend && pytest -q tests/evaluation_v2 \
  tests/test_evaluation_manifest.py \
  tests/test_policy_compiler.py \
  tests/test_policy_store.py \
  tests/test_partner_decision_fallback.py \
  tests/test_on_demand_lookup_independent.py \
  tests/test_pipeline_execution_contract.py \
  tests/test_pipeline_execution_semantics.py \
  tests/test_api_worker_prerequisites.py \
  tests/jobs/test_job_handlers.py \
  tests/monitoring/test_monitoring_repository_unit.py
# 521 passed in 2.79s

cd backend && pytest -q
# 1,193 passed, 10 skipped, 1 warning in 10.04s

cd backend && pytest -q -rs
# 1,193 passed, 10 environment-gated skips, 1 warning in 10.30s

cd backend && pytest -q \
  tests/evaluation_v2/test_decision_safety_certification.py -rs
# 18 passed, 0 skipped in 0.09s

cd app-front-end && npm test -- --run
# 58 test files passed; 271 tests passed in 8.51s

cd app-front-end && npm run lint
# exit 0

cd app-front-end && npm run build
# exit 0; 865 modules transformed

cd backend && python3 scripts/run_golden_set.py --version v7 --json
# 27 passed, 0 failed; exit 0

cd backend && python3 scripts/check_phase8_readiness.py --json
# code checks passed; direct_database_dsn blocked; ready=false; exit 1
```

Skip inspection with `pytest -q -rs`: the focused suite has no skips. The 10
full-suite skips are six target-PostgreSQL cases (one
Fund Intelligence repository case, two identity repository cases, two job
repository cases, and the Phase 1 acceptance case) plus four live integrations
(`test_end_to_end.py`, `test_partner_flow.py`, `test_portfolio_layer.py`, and
`test_scouts.py`). They are all explicitly environment-gated. No
decision-safety certification case was skipped.

The one warning is the existing `StarletteDeprecationWarning` from FastAPI's
`TestClient` importing deprecated `httpx` compatibility; it is unrelated to
the evaluation behavior certified here.

### Certification limits

This is a code-level, local executable safety certification only. It does not
certify target PostgreSQL, migration application, RLS, database triggers,
transaction races, service-role permissions, or authority-control migration
readiness. Target PostgreSQL certification remains pending until a DSN is
configured. Authority-control implementation and certification remain pending
as their own subsequent slice; this branch must not claim that cutover yet.

## Rollout recommendation

Roll out to one internal/solo-GP tenant first. Apply migrations, run Phase 2 backfill/reconciliation, run the Phase 8 gate, then enable UI surfaces in this order: identity queue, evidence/evaluation read views, human rulings, actions/monitoring, Fund Intelligence, imports, outcomes. Observe budget reservations, blocked jobs, identity-review volume, proposal rejection memory, outcome coverage, and outbox health before adding tenants.

Rollback disables new intake and workers but retains all append-only records. Do not drop claims, evaluations, rulings, proposals, outcomes, jobs, or outbox entries; they are the audit and recovery trail.
