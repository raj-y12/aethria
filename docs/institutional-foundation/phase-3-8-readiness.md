# Phase 3–8 institutional domain readiness

Date: 2026-07-21

## Outcome

The code-level evidence-and-decision platform and authority-control cutover are
implemented through Phase 8, including the round-four concurrency, policy,
isolation, readiness, and provenance remediation. They are deliberately **not
certified for production in this local workspace** because no `DATABASE_URL`,
`SUPABASE_DB_URL`, or `TEST_DATABASE_URL` is configured. The migrations,
immutable database triggers, RLS, transaction races, and service-role
permissions therefore have not been exercised against the target PostgreSQL
instance.

The product authority model is now explicit: agents discover, extract, evaluate, recommend, draft, monitor, and propose; authenticated people rule, approve external actions, correct evidence, resolve identity, accept policy proposals, and publish policy.

## Round-3 remediation certification (2026-07-21)

The interrupted scoring-runtime work was completed and integrated with exact
consensus traces, typed stage outcomes, attempt-aware lookup outcomes, live
materiality-schema readiness, atomic tenant policy upgrade, immutable
evaluation manifests, and behaviorally authoritative Partner rules. The local
backend, frontend, golden, and code-readiness gates were all rerun from the
final branch state. Target-PostgreSQL and live-provider gates remain explicitly
uncertified because their credentials are not present in this workspace.

## Round-4 authority-cutover remediation (2026-07-21)

The final audit findings are remediated in code. Durable workers now fence
every terminal write by lease ownership; lookup attempts commit their terminal
job and durable outcome together; governed Partner decisions use one certified
threshold authority; Meta reports per-target failures; policy upgrade patches
only the active policy pointer under row lock; lookup outcomes have an explicit
service-role-only RLS/grant contract; agent status reports the same execution
prerequisites as the runner; and evaluation-manifest v3 records executed,
reused, and not-run identities without attributing unused models to a run.

This is a local code certification, not a target-database certification. The
three round-four PostgreSQL-focused tests and the seven PostgreSQL-focused full
suite tests remain skipped until an operator supplies `TEST_DATABASE_URL`.

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
- Published policy identity covers the normalized dimensions, decision thresholds, and score bands actually consumed. Evaluation-manifest v3 records per-stage and per-prompt `executed`, `reused`, and `not_run` identities, carries the source run for reused artifacts, omits unused model identities, and validates Partner's persisted prompt hash against independently captured invocation evidence without reloading mutable settings or global rules.
- Governed score precision remains lossless through review aggregation, persistence adapters, and Partner boundaries, including immediately around pass and advance thresholds.
- The active v4 Partner policy is compiled once into an immutable, extra-forbid typed contract; every configurable decision field has an explicit runtime consumer and changes the recorded rules identity. Redundant v3 threshold/boundary declarations and fixed safety-action literals were removed rather than treated as decorative configuration. Historical v3 remains strict and parseable.
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
8. `20260721130000_upgrade_fund_policy_rpc.sql`
9. `20260721143000_patch_upgrade_fund_policy_settings.sql`
10. `20260721150000_lookup_job_outcomes_rls.sql`

Do not expose the new UI before the first seven migrations and Phase 0–2
dependencies are applied. Apply migrations 8 and 9 before running the
published-policy upgrade procedure below. Apply migration 10 before accepting
durable lookup jobs: it enables RLS on `lookup_job_outcomes`, removes inherited
table privileges, and grants CRUD only to `service_role` under an explicit
service-role policy. The repositories intentionally fail closed when their
direct PostgreSQL store is unavailable.

The readiness gate checks both the Supabase migration ledger and the live
`information_schema.columns` projection. Migration `20260720120000` is ready
only when these exact compatible columns are present as PostgreSQL `text`:

- `evaluation_runs.evidence_materiality_digest`
- `material_change_checks.previous_materiality_digest`
- `material_change_checks.current_materiality_digest`

A recorded migration version without all three live columns (or with a
different type) remains not ready. Without a direct database DSN, readiness
also remains false because neither the ledger nor the live schema can be
certified. The same live gate checks that migration 10 is recorded, RLS is
enabled, the service-role policy exists with exact
`auth.role() = 'service_role'` predicates, PUBLIC/anon/authenticated privileges
are absent, and service-role CRUD privileges are present.

## Published-policy upgrade procedure

Legacy or missing active policy rows remain a typed
`published_policy_required` prerequisite block. They are not automatically
reinterpreted. Upgrade one tenant at a time from an operator-reviewed current
`fund_config` JSON object (or a settings JSON object containing `fund_config`):

```bash
cd backend

# 1. Inspect the exact old/new IDs and hashes; this performs no writes.
python3 scripts/upgrade_published_policy.py \
  --user-id '<clerk-user-id>' \
  --fund-config-file /absolute/path/to/operator-selected-fund-config.json \
  --dry-run --json

# 2. After the operator approves that transition, append and activate it atomically.
python3 scripts/upgrade_published_policy.py \
  --user-id '<clerk-user-id>' \
  --fund-config-file /absolute/path/to/operator-selected-fund-config.json \
  --apply --json

# 3. Re-run with the same selected config; status must be already_current.
python3 scripts/upgrade_published_policy.py \
  --user-id '<clerk-user-id>' \
  --fund-config-file /absolute/path/to/operator-selected-fund-config.json \
  --dry-run --json
```

Apply uses the service-role-only `upgrade_fund_policy` RPC. It locks the exact
tenant settings row, compare-and-swaps the old active ID/hash, appends the
strict normalized and hash-verified bundle, and merges only the new active
policy ID/hash into the latest settings document in one PostgreSQL transaction.
The client sends a pointer-only patch, so concurrent changes to budgets, agent
toggles, fund identity, or other settings survive the upgrade. Compile,
storage, conflict, or pointer failures leave the historical row and pointer
unchanged. A successful rerun is idempotent. Never use a legacy policy row as
the input JSON; select the current operator-approved fund configuration
explicitly.

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
- Required round-4 focused suite: 163 passed, 3 target-PostgreSQL skips, 1 warning.
- Required round-3 focused suite: 698 passed, 0 skipped.
- Partner v4 decision-safety certification: 18 passed, 0 skipped.
- Full backend suite, run twice: 1,430 passed, 11 skipped, 1 warning on each run.
- Decision-safety certification: all 18 cases ran and passed; no certification case was skipped.
- Frontend: 59 test files and 274 tests passed; lint and production build passed (866 modules transformed).
- Readiness code checks: golden set, migration/schema requirements, atomic pointer-only policy-upgrade migration, lookup-outcome RLS migration, and proposal-only Meta mutation paths passed.
- Direct database readiness: blocked by missing DSN (`ready: false`, expected in this workspace).
- Target migration application, RLS enforcement, UUID/JSON codecs, triggers, foreign keys, and transactional race behavior: not certified locally.
- Authority-control behavior: code-certified by the local suites above; target-database enforcement remains uncertified.

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
`resources/config/partner_rules/v4.json` contract, so its thresholds,
eligibility rules, confidence caps, freshness behavior, and decisive claim
lists are the same versioned inputs exercised by the test. Fixed comparison and
evidence-safety clamps are materialized by the evaluator and certified as
non-configurable invariants.

Observed on 2026-07-21 from this worktree:

```bash
cd backend && pytest -q -rs \
  tests/evaluation_v2/test_partner_rules_round4_authority.py \
  tests/identity/test_lookup_identity_admission.py \
  tests/jobs/test_api_durable_enqueue.py \
  tests/jobs/test_job_endpoints.py \
  tests/jobs/test_job_handlers.py \
  tests/jobs/test_job_repository_postgres.py \
  tests/jobs/test_job_repository_unit.py \
  tests/jobs/test_job_worker.py \
  tests/jobs/test_lookup_outcomes_security.py \
  tests/outcomes/test_phase8_readiness_schema.py \
  tests/test_evaluation_manifest.py \
  tests/test_lookup_status_independent.py \
  tests/test_meta_analysis_only.py \
  tests/test_meta_target_outcomes.py \
  tests/test_partner_decision_fallback.py \
  tests/test_policy_upgrade.py \
  tests/test_policy_upgrade_migration.py
# 163 passed, 3 target-PostgreSQL skips, 1 warning in 2.25s

cd backend && pytest -q tests/evaluation_v2 \
  tests/test_evaluation_manifest.py \
  tests/test_policy_compiler.py \
  tests/test_policy_store.py \
  tests/test_partner_decision_fallback.py \
  tests/test_pipeline_execution_contract.py \
  tests/test_pipeline_execution_semantics.py \
  tests/test_api_worker_prerequisites.py \
  tests/test_on_demand_lookup_independent.py \
  tests/jobs/test_job_handlers.py \
  tests/monitoring \
  tests/test_run_system_cli_gate.py
# 698 passed in 5.05s

cd backend && pytest -q
# 1,430 passed, 11 skipped, 1 warning in 12.48s

cd backend && pytest -q -rs
# 1,430 passed, 11 environment-gated skips, 1 warning in 13.07s

cd backend && pytest -q \
  tests/evaluation_v2/test_decision_safety_certification.py -rs
# 18 passed, 0 skipped in 0.11s

cd app-front-end && npm test -- --run
# 59 test files passed; 274 tests passed in 26.39s

cd app-front-end && npm run lint
# exit 0

cd app-front-end && npm run build
# exit 0; 866 modules transformed

cd backend && python3 scripts/run_golden_set.py --version v7 --json
# 27 passed, 0 failed; exit 0

cd backend && python3 scripts/check_phase8_readiness.py --json
# golden/migrations/policy-upgrade/lookup-RLS/meta checks passed;
# direct_database_dsn blocked; ready=false

git diff --check 5bab009f..HEAD
# exit 0
```

Skip inspection with `pytest -q -rs`: the round-3 and decision-safety focused
suites have no skips. The round-4 focused suite skips three target-PostgreSQL
job-repository cases because `TEST_DATABASE_URL` is absent. The 11 full-suite
skips are seven target-PostgreSQL cases (one Fund Intelligence repository case,
two identity repository cases, three job repository cases, and the Phase 1
acceptance case) plus four live integrations
(`test_end_to_end.py`, `test_partner_flow.py`, `test_portfolio_layer.py`, and
`test_scouts.py`). They are all explicitly environment-gated. No
decision-safety certification case was skipped.

The one warning is the existing `StarletteDeprecationWarning` from FastAPI's
`TestClient` importing deprecated `httpx` compatibility; it is unrelated to
the evaluation behavior certified here.

### Certification limits

This is a code-level, local executable safety certification only. It does not
certify target PostgreSQL, migration application, live RLS, database triggers,
transaction races, or service-role permissions. Target PostgreSQL enforcement
certification remains pending until a DSN is configured; this branch must not
claim production database certification from static migration checks.

## Rollout recommendation

Roll out to one internal/solo-GP tenant first. Apply migrations, run Phase 2 backfill/reconciliation, run the Phase 8 gate, then enable UI surfaces in this order: identity queue, evidence/evaluation read views, human rulings, actions/monitoring, Fund Intelligence, imports, outcomes. Observe budget reservations, blocked jobs, identity-review volume, proposal rejection memory, outcome coverage, and outbox health before adding tenants.

Rollback disables new intake and workers but retains all append-only records. Do not drop claims, evaluations, rulings, proposals, outcomes, jobs, or outbox entries; they are the audit and recovery trail.
