# Phase 3–8 institutional domain readiness

Date: 2026-07-15

## Outcome

The code-level evidence-and-decision platform is implemented through Phase 8. It is deliberately **not certified for production in this local workspace** because no `DATABASE_URL`, `SUPABASE_DB_URL`, or `TEST_DATABASE_URL` is configured. The migrations, immutable database triggers, RLS, transaction races, and service-role permissions therefore have not been exercised against the target PostgreSQL instance.

The product authority model is now explicit: agents discover, extract, evaluate, recommend, draft, monitor, and propose; authenticated people rule, approve external actions, correct evidence, resolve identity, accept policy proposals, and publish policy.

## Implemented behavior

### Evidence and founder assessment

- Artifacts, evidence items, claims, claim/evidence links, plans, and corrections are separate tenant-scoped records.
- Material externally verified claims require evidence links.
- Unsupported model-generated personality labels such as “magnetic founder” are rejected. Subjective interview observations require operator attribution.
- Restricted storage references are not exposed by the ledger API. Deck/email intake registers confidential, untrusted artifact metadata with explicit retention policy.
- Prompt-injection indicators are recorded on untrusted artifacts; document content cannot select providers, policies, recipients, or budgets.

### Evaluation and recommendation

- Evaluation runs snapshot claims and relationships under deterministic hashes and record policy, rubric, partner-rule, model, and prompt dependencies.
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
- Scheduled refresh performs a cheap claim-snapshot materiality check before creating deeper work.
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

Do not expose the new UI before all six migrations and Phase 0–2 dependencies are applied. The repositories intentionally fail closed when their direct PostgreSQL store is unavailable.

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
- Focused Phase 2–8 suite: 162 passed, 3 skipped before the final golden/readiness additions.
- Readiness code checks: migration files present; Meta mutation paths proposal-only.
- Direct database readiness: blocked by missing DSN.
- Target migration application, RLS enforcement, UUID/JSON codecs, triggers, foreign keys, and transactional race behavior: not certified locally.

## Rollout recommendation

Roll out to one internal/solo-GP tenant first. Apply migrations, run Phase 2 backfill/reconciliation, run the Phase 8 gate, then enable UI surfaces in this order: identity queue, evidence/evaluation read views, human rulings, actions/monitoring, Fund Intelligence, imports, outcomes. Observe budget reservations, blocked jobs, identity-review volume, proposal rejection memory, outcome coverage, and outbox health before adding tenants.

Rollback disables new intake and workers but retains all append-only records. Do not drop claims, evaluations, rulings, proposals, outcomes, jobs, or outbox entries; they are the audit and recovery trail.
