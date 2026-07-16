# Canonical Identity and Source Observations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make source observations, tenant-scoped canonical companies, identifiers, ambiguity cases, and opportunities authoritative before any legacy startup projection is created.

**Architecture:** Add a focused `identity/` domain package backed by direct PostgreSQL transactions. Manual lookups and autonomous discoveries first write a `SourceObservation`, resolve it by verified domain/provider identifiers, then either create/link a `Company` and `Opportunity` or open an `IdentityResolutionCase`. Existing `startups` rows remain a compatibility projection linked by `Opportunity.legacy_startup_id`; authoritative writes and their outbox event commit together.

**Tech Stack:** Python 3.13, Pydantic v2, asyncpg/PostgreSQL 14+, FastAPI, Supabase migrations, pytest, existing resolver and durable outbox.

## Global Constraints

- Every model, query, unique constraint, and API lookup is tenant-scoped by explicit `user_id`.
- Verified canonical domains and provider identifiers may identify a company; normalized names alone never auto-merge.
- Ambiguous observations persist as open identity cases and block evaluation.
- Existing `startups` routes remain compatibility projections during the strangler migration.
- New migrations are additive; never edit an existing migration.
- Authoritative institutional records and their outbox event commit in one direct-PostgreSQL transaction.
- `USE_SUPABASE_STORAGE=1`, an active FundThesis for autonomous acquisition, cost gates, reference validation, and the direct job DSN remain hard gates.
- Manual lookup reuses the picker `CompanyResolution`; it does not run identity retrieval twice.
- Phase 2 backend delivery records the exact frontend contracts, but does not modify frontend source in this backend execution stream.

---

## File map

- `supabase/migrations/20260715210000_canonical_identity.sql` — additive identity/opportunity schema, constraints, indexes, RLS, service-role grants.
- `backend/identity/models.py` — Pydantic commands and authoritative record contracts.
- `backend/identity/normalization.py` — canonical domain, provider identifier, alias, and source-channel normalization.
- `backend/identity/repository.py` — direct-PostgreSQL transactional persistence, identity claims, case resolution, projection linking, and reconciliation reads.
- `backend/identity/service.py` — domain-first resolution rules; no storage or API formatting logic.
- `backend/identity/projection.py` — compatibility-projection linkage and replay/reconciliation state.
- `backend/identity/backfill.py` — conservative, restartable startup-to-observation backfill.
- `backend/routers/identity.py` — tenant-scoped company, opportunity, observation, and identity-case APIs.
- `backend/jobs/handlers.py` — continuous manual lookup path invokes identity admission before legacy scout/review/partner work.
- `backend/scout/engine.py` and `backend/pipeline_runner.py` — autonomous discoveries emit authoritative observations and projection linkage.
- `backend/scripts/backfill_canonical_identity.py` — dry-run/apply operator command.
- `backend/scripts/check_identity_reconciliation.py` — tenant-safe projection drift report.
- `resources/evaluation/golden_set/v2.json` and `backend/evaluation/golden_set.py` — Phase 2 identity invariants.

### Task 1: Add canonical identity contracts and schema

**Files:**
- Create: `backend/identity/__init__.py`
- Create: `backend/identity/models.py`
- Create: `supabase/migrations/20260715210000_canonical_identity.sql`
- Test: `backend/tests/identity/test_identity_models.py`
- Test: `backend/tests/identity/test_identity_migration.py`

**Interfaces:**
- Consumes: explicit tenant validation from `tenant_context.require_user_id`.
- Produces: `SourceChannel`, `IdentityStatus`, `OpportunityState`, `SourceObservationInput`, `IdentityCandidate`, `IdentityAdmission`, and authoritative row DTOs used by all later Phase 2 tasks.

- [ ] **Step 1: Write failing model and migration tests**

```python
def test_observation_requires_explicit_tenant_and_channel():
    value = SourceObservationInput(
        user_id="fund-a", channel="manual_lookup", observed_name="Acme"
    )
    assert value.user_id == "fund-a"
    with pytest.raises(ValueError):
        SourceObservationInput(user_id="", channel="manual_lookup", observed_name="Acme")

def test_identity_migration_is_tenant_scoped_and_additive():
    sql = MIGRATION.read_text().lower()
    for table in ("companies", "company_identifiers", "company_aliases", "source_observations", "opportunities", "identity_resolution_cases"):
        assert f"create table if not exists public.{table}" in sql
        assert "user_id text not null" in sql
    assert "where verification_status = 'verified'" in sql
    assert "alter table public.companies enable row level security" in sql
```

- [ ] **Step 2: Run the tests and observe missing contracts/schema**

Run: `python3 -m pytest -q backend/tests/identity/test_identity_models.py backend/tests/identity/test_identity_migration.py`

Expected: collection/import failure for `identity.models` and missing migration.

- [ ] **Step 3: Implement Pydantic contracts**

Define exact enum values:

```python
class SourceChannel(str, Enum):
    MANUAL_LOOKUP = "manual_lookup"
    AUTONOMOUS_DISCOVERY = "autonomous_discovery"
    INBOUND = "inbound"
    OUTBOUND = "outbound"
    REFERRAL = "referral"
    EVENT = "event"
    PORTFOLIO_INTRO = "portfolio_intro"
    IMPORT = "import"
    BACKFILL = "backfill"

class IdentityStatus(str, Enum):
    PENDING = "pending"
    RESOLVED = "resolved"
    AMBIGUOUS = "ambiguous"
    DEFERRED = "deferred"
    REJECTED = "rejected"

class OpportunityState(str, Enum):
    DISCOVERED = "discovered"
    IDENTITY_REVIEW = "identity_review"
    ACTIVE_REVIEW = "active_review"
    MONITOR = "monitor"
    ADVANCE = "advance"
    PASS = "pass"
    INVESTED = "invested"
    ARCHIVED = "archived"
```

`SourceObservationInput` requires `user_id`, `channel`, `observed_name`, optional observed domain/provider IDs, external event key, source metadata, picker resolution, and observation time. `IdentityAdmission` returns observation, optional company/opportunity/case IDs, status, confidence, matched identifier, and `blocks_evaluation`.

- [ ] **Step 4: Add the migration**

Create tenant-scoped tables with UUID primary keys, composite `(user_id, id)` uniqueness for foreign keys, partial verified-identifier uniqueness on `(user_id, identifier_type, normalized_value)`, idempotent source-event uniqueness, opportunity context uniqueness, indexes for domain/case/queue reads, RLS, service-role-only policies/grants, and timestamp triggers. Add nullable current evaluation/recommendation/ruling pointers for later phases without foreign keys until their tables exist.

- [ ] **Step 5: Run tests and commit**

Run: `python3 -m pytest -q backend/tests/identity/test_identity_models.py backend/tests/identity/test_identity_migration.py`

Expected: PASS.

Commit: `git commit -m "feat: add canonical identity schema"`

### Task 2: Implement deterministic normalization and domain-first matching

**Files:**
- Create: `backend/identity/normalization.py`
- Create: `backend/identity/service.py`
- Test: `backend/tests/identity/test_identity_normalization.py`
- Test: `backend/tests/identity/test_identity_service.py`

**Interfaces:**
- Consumes: `CompanyResolution`, `SourceObservationInput`, and a repository exposing `find_verified_identifier`, `create_company_admission`, and `open_identity_case`.
- Produces: `normalize_domain(value) -> str | None`, `extract_identifier_candidates(observation) -> list[NormalizedIdentifier]`, and `IdentityService.admit(observation) -> IdentityAdmission`.

- [ ] **Step 1: Write failing table-driven tests**

Cover exact domains, schemes/paths, `www`, platform URLs, aliases, same-name/different-domain companies, conflicting provider IDs, no domain, two strong picker candidates, and tenant separation. Assert names never auto-merge.

```python
@pytest.mark.parametrize(("raw", "expected"), [
    ("https://www.Acme.com/about", "acme.com"),
    ("acme.co.uk", "acme.co.uk"),
    ("https://linkedin.com/company/acme", None),
])
def test_normalize_domain(raw, expected):
    assert normalize_domain(raw) == expected
```

- [ ] **Step 2: Run and observe failure**

Run: `python3 -m pytest -q backend/tests/identity/test_identity_normalization.py backend/tests/identity/test_identity_service.py`

- [ ] **Step 3: Implement normalization**

Use the existing `registrable_domain` helper. Provider URLs normalize to provider-specific IDs, not canonical domains. Normalize aliases for display/search only. Reject news/directory/social hosts as company-domain identifiers.

- [ ] **Step 4: Implement resolution rules**

Rules in order:

1. Exact verified domain match in the same tenant resolves.
2. Exact verified provider identifier match resolves when all verified identifiers point to one company.
3. Conflicting matches open an ambiguity case.
4. Two picker candidates above `IDENTITY_AUTO_RESOLVE_CONFIDENCE` open an ambiguity case.
5. A picker-confirmed domain or one candidate above the threshold creates a company with that domain.
6. A source with no safe identifier opens an identity case; normalized name cannot resolve it.

The service stores no data directly and never calls an LLM.

- [ ] **Step 5: Register `IDENTITY_AUTO_RESOLVE_CONFIDENCE=0.85`, update `.env.example`, run tests, commit**

Run: `python3 -m pytest -q backend/tests/identity/test_identity_normalization.py backend/tests/identity/test_identity_service.py backend/tests/test_config_registry.py`

Commit: `git commit -m "feat: resolve companies by verified identifiers"`

### Task 3: Add the transactional identity repository

**Files:**
- Create: `backend/identity/repository.py`
- Test: `backend/tests/identity/test_identity_repository_unit.py`
- Test: `backend/tests/identity/test_identity_repository_postgres.py`

**Interfaces:**
- Consumes: an asyncpg pool and Phase 2 model contracts.
- Produces: `IdentityRepository.record_observation`, `find_verified_identifier`, `create_company_admission`, `open_identity_case`, `resolve_case`, `link_legacy_projection`, `get_company`, `get_opportunity`, `list_cases`, and `reconciliation_counts`.

- [ ] **Step 1: Write transaction and tenant tests**

Assert one transaction contains observation + company/identifier/opportunity + `observation_resolved` outbox insert; idempotent external event returns the existing observation; verified identifier races converge; cross-tenant reads return no row; ambiguity creates no opportunity; projection linking is conditional and idempotent.

- [ ] **Step 2: Run and observe missing repository**

Run: `python3 -m pytest -q backend/tests/identity/test_identity_repository_unit.py`

- [ ] **Step 3: Implement repository operations**

Use `SELECT … FOR UPDATE` around verified identifier claims. Every SQL predicate includes `user_id`. `create_company_admission` inserts the observation if needed, company, verified/unverified identifiers, alias, opportunity, and an `observation_resolved` domain-outbox event in one transaction. `open_identity_case` commits observation + case + `identity_case.opened` event, with no company/opportunity.

- [ ] **Step 4: Add target-PostgreSQL tests**

Gate with `TEST_DATABASE_URL`. Prove two concurrent observations with the same verified domain yield one company, two opportunities only when context keys differ, and no cross-tenant leakage.

- [ ] **Step 5: Run and commit**

Run: `python3 -m pytest -q backend/tests/identity/test_identity_repository_unit.py backend/tests/identity/test_identity_repository_postgres.py`

Commit: `git commit -m "feat: persist canonical identity transactionally"`

### Task 4: Admit manual lookups before legacy pipeline execution

**Files:**
- Modify: `backend/jobs/handlers.py`
- Modify: `backend/pipeline_runner.py`
- Create: `backend/identity/projection.py`
- Test: `backend/tests/identity/test_lookup_identity_admission.py`
- Test: `backend/tests/jobs/test_job_handlers.py`

**Interfaces:**
- Consumes: `IdentityService.admit`, the durable job repository pool, picker `CompanyResolution`, and the existing continuous lookup chain.
- Produces: checkpoints `identity` and `projection`, institutional IDs in checkpoint metadata, and `Opportunity.legacy_startup_id` linkage.

- [ ] **Step 1: Write failing integration-unit tests**

Assert identity admission occurs before `run_on_demand_lookup`; the serialized picker result is reused; ambiguous admission raises a structured blocked-job error and never calls Scout; successful legacy output links the opportunity; legacy persistence failure leaves authoritative observation/opportunity recoverable; rerun uses the existing opportunity rather than creating a second one.

- [ ] **Step 2: Run and observe failure**

Run: `python3 -m pytest -q backend/tests/identity/test_lookup_identity_admission.py backend/tests/jobs/test_job_handlers.py`

- [ ] **Step 3: Add structured blocked-job handling**

Add `JobExecutionBlocked(code, recovery_action)` to `jobs.models`. Worker calls repository `block(...)`, which stores a safe code/detail and publishes `agent_job.blocked`; it does not consume retry attempts automatically.

- [ ] **Step 4: Integrate identity admission**

`company_lookup_handler` creates `IdentityRepository(repository.pool)`, records an observation with channel `manual_lookup`, and checkpoints only IDs/status/confidence. If ambiguity exists, block with `identity_review_required`. Otherwise pass institutional IDs to `run_on_demand_lookup` as optional context and link the returned startup ID after Scout persistence.

- [ ] **Step 5: Run compatibility tests and commit**

Run: `python3 -m pytest -q backend/tests/identity/test_lookup_identity_admission.py backend/tests/jobs/test_job_handlers.py backend/tests/test_on_demand_lookup_independent.py backend/tests/test_lookup_rerun.py`

Commit: `git commit -m "feat: admit lookups through canonical identity"`

### Task 5: Admit autonomous discoveries and maintain compatibility linkage

**Files:**
- Modify: `backend/scout/engine.py`
- Modify: `backend/pipeline_runner.py`
- Modify: `backend/identity/projection.py`
- Test: `backend/tests/identity/test_autonomous_identity_admission.py`
- Test: `backend/tests/test_pipeline_reference_prune.py`

**Interfaces:**
- Consumes: validated Scout results after mandatory reference validation and the same `IdentityService` used by manual lookup.
- Produces: channel `autonomous_discovery` observations and linked opportunities; ambiguous results stop before reviewer evaluation.

- [ ] **Step 1: Write failing discovery tests**

Assert two scout personas observing the same verified domain create two observations but one company/opportunity context; source persona/channel attribution is preserved; same normalized name with different domains creates distinct companies; ambiguity prevents reviewer/partner execution; reference-pruned discoveries never create authoritative observations.

- [ ] **Step 2: Run and observe failure**

Run: `python3 -m pytest -q backend/tests/identity/test_autonomous_identity_admission.py backend/tests/test_pipeline_reference_prune.py`

- [ ] **Step 3: Add a post-validation acquisition callback**

Return typed validated Scout payloads from `ScoutEngine.run_cycle` and invoke identity admission in the owning pipeline runner after reference validation. Do not add a second retrieval pass. Link any compatibility startup ID to the resulting opportunity.

- [ ] **Step 4: Add projection replay semantics**

`identity/projection.py` exposes idempotent linkage/replay functions. A stale missing `legacy_startup_id` is repairable from observation lookup IDs or exact startup IDs; replay never creates a second institutional record.

- [ ] **Step 5: Run and commit**

Run: `python3 -m pytest -q backend/tests/identity/test_autonomous_identity_admission.py backend/tests/test_pipeline_reference_prune.py backend/tests/test_lookup_in_memory_handoff.py`

Commit: `git commit -m "feat: unify autonomous sourcing on canonical identity"`

### Task 6: Add conservative legacy backfill and reconciliation

**Files:**
- Create: `backend/identity/backfill.py`
- Create: `backend/scripts/backfill_canonical_identity.py`
- Create: `backend/scripts/check_identity_reconciliation.py`
- Test: `backend/tests/identity/test_identity_backfill.py`
- Test: `backend/tests/identity/test_identity_reconciliation.py`

**Interfaces:**
- Consumes: existing tenant-scoped startup rows and the IdentityRepository.
- Produces: restartable dry-run/apply reports and drift counts without exposing private row content.

- [ ] **Step 1: Write failing backfill tests**

Cover exact verified domains merging, name-only rows remaining distinct, legacy `YES/MAYBE/NO` opportunity-state projection through the sole compatibility adapter, preserved source/resolver JSON, idempotent rerun, per-tenant counts, and interrupted-batch resume.

- [ ] **Step 2: Run and observe failure**

Run: `python3 -m pytest -q backend/tests/identity/test_identity_backfill.py backend/tests/identity/test_identity_reconciliation.py`

- [ ] **Step 3: Implement dry-run/apply backfill**

Require `--user-id`; default dry-run; `--apply` writes bounded batches. Treat legacy domains as unverified unless resolver evidence confirms them. Never infer verification from a company name. Preserve the raw legacy scout/resolution payload in observation metadata.

- [ ] **Step 4: Implement reconciliation**

Report counts for legacy rows, observations, companies, opportunities, unlinked projections, duplicate verified identifiers, open cases, and tenant drift. Exit nonzero on authoritative legacy-only rows created after Phase 2 activation or identifier constraint violations.

- [ ] **Step 5: Run and commit**

Run: `python3 -m pytest -q backend/tests/identity/test_identity_backfill.py backend/tests/identity/test_identity_reconciliation.py`

Commit: `git commit -m "feat: backfill and reconcile canonical identity"`

### Task 7: Expose identity and opportunity APIs

**Files:**
- Create: `backend/routers/identity.py`
- Modify: `backend/api.py`
- Test: `backend/tests/identity/test_identity_endpoints.py`

**Interfaces:**
- Consumes: runtime identity repository on `app.state` and Clerk-authenticated `request.state.user_id`.
- Produces: `GET /api/companies/{id}`, `GET /api/opportunities/{id}`, `GET /api/observations`, `GET /api/identity-cases`, `POST /api/identity-cases/{id}/resolve`, `/defer`, and `/reject`.

- [ ] **Step 1: Write failing endpoint tests**

Assert cross-tenant 404s, bounded pagination, safe candidate evidence, explicit match/create/defer/reject actions, operator correction audit metadata, idempotent repeated resolution, and no raw provider/DB errors.

- [ ] **Step 2: Run and observe 404/missing router**

Run: `python3 -m pytest -q backend/tests/identity/test_identity_endpoints.py`

- [ ] **Step 3: Implement router and mount it**

Validate UUID route IDs. Resolving a case calls one repository transaction that selects/creates a company, links the observation, creates an opportunity, supersedes the case state, and writes `identity_case.resolved` to the outbox. Never trust a client-supplied tenant ID.

- [ ] **Step 4: Run security regression and commit**

Run: `python3 -m pytest -q backend/tests/identity/test_identity_endpoints.py backend/tests/test_security_api.py`

Commit: `git commit -m "feat: expose identity resolution controls"`

### Task 8: Extend the golden set and Phase 2 readiness gate

**Files:**
- Create: `resources/evaluation/golden_set/v2.json`
- Modify: `backend/evaluation/golden_set.py`
- Create: `backend/tests/identity/test_golden_set_v2.py`
- Create: `docs/institutional-foundation/phase-2-readiness.md`
- Modify: `docs/institutional-foundation/frontend-impact-ledger.md`

**Interfaces:**
- Consumes: the nine v1 cases plus Phase 2 identity snapshots.
- Produces: executable v2 invariants and an operator rollout gate.

- [ ] **Step 1: Add failing v2 tests**

For every representative case pin source-observation preservation, canonical company match or non-match, ambiguity outcome, opportunity creation/blocking, source channels, and legacy linkage. Include same-name different-domain, cross-channel deduplication, and repeat-idempotency cases.

- [ ] **Step 2: Implement v2 corpus/runner support**

Extend version allowlisting without changing v1 assertions. V2 checks exact Phase 2 paths only and does not claim evidence-ledger semantics.

- [ ] **Step 3: Record readiness and frontend impact**

Document migration order, backfill dry-run counts, reconciliation output, open-case operational ownership, rollback, and the exact required Dispatch/Flow identity-case components.

- [ ] **Step 4: Run complete Phase 2 verification**

```bash
python3 -m pytest -q backend/tests/identity backend/tests/jobs \
  backend/tests/test_company_resolver.py backend/tests/test_lookup_rerun.py \
  backend/tests/test_pipeline_reference_prune.py backend/tests/test_security_api.py
cd backend && python3 scripts/run_golden_set.py --version v2 --json
```

Expected: all non-live tests pass; target-PostgreSQL tests skip only when `TEST_DATABASE_URL` is absent.

- [ ] **Step 5: Commit**

Commit: `git commit -m "test: add canonical identity readiness gate"`

## Self-review

- Spec coverage: schema, domain-first matching, ambiguity, source attribution, manual and autonomous admission, transactional outbox, conservative backfill, projection replay/reconciliation, APIs, v2 golden set, and frontend contract are each owned by a task.
- Placeholder scan: no TBD/TODO/future implementation placeholders are present; later evidence/evaluation foreign keys are deliberately nullable phase boundaries defined by the master design.
- Type consistency: every later task uses the Task 1 contracts and Task 3 repository names; `IdentityAdmission` is the single service result throughout.
- Rollout safety: no name-only merge, no legacy-only authoritative success after activation, and no evaluation of unresolved identity.
