# Authority Control Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make canonical records the sole write authority for an explicitly activated tenant while preserving a replayable, one-way `startups` compatibility projection and a reversible rollout.

**Architecture:** Add a tenant-scoped rollout state machine and canonical workflow state to the existing `opportunities` authority. Canonical mutations append domain-outbox events in the same PostgreSQL transaction; a projector consumes events through an idempotent receipt ledger and writes only legacy display fields. API reads and writes select the canonical or legacy path from the rollout mode, with conditional version/fencing checks and a rollback operation that pauses canonical work without deleting records.

**Tech Stack:** FastAPI, Pydantic v2, asyncpg/PostgreSQL, Supabase service-role migrations, existing `IdentityRepository`, `DecisionRepository`, `evaluation_v2.Repository`, `domain_outbox`, TanStack Query, pytest, Vitest.

## Global Constraints

- Every repository and service receives an explicit non-empty `user_id` and calls `require_user_id()` at its boundary.
- `legacy -> shadow -> backfill -> canonical_write -> canonical_read` is the only legal rollout order; rollback moves traffic to legacy and preserves canonical append-only records.
- `workflow_state` is separate from `decision_state`; `decision_state` remains a compatibility projection until canonical reads are active.
- Canonical writes and their outbox event commit in one PostgreSQL transaction.
- Projection consumers are idempotent, replayable, tenant-scoped, and never write canonical tables.
- A stale worker or stale rollout version cannot mutate canonical or projected authority.
- Only `HumanRulingDecision.INVEST` may create a portfolio command; this plan only establishes the event boundary consumed by the later portfolio slice.
- Migrations are append-only; target PostgreSQL and RLS/service-role checks remain environment-gated when no DSN exists.

## File Map

- Create `supabase/migrations/20260722090000_authority_control.sql`: rollout records, workflow columns, event receipts, canonical transition constraints, RLS, and service-role grants.
- Create `backend/authority/models.py`: rollout modes, workflow states, block codes, transition and receipt Pydantic models.
- Create `backend/authority/repository.py`: transactional rollout reads/transitions, workflow transitions, and receipt claims.
- Create `backend/authority/service.py`: tenant authority guard, legal-mode transitions, rollback/fencing decisions, and canonical-write selection.
- Create `backend/authority/projection.py`: pure event-to-legacy patch mapping and idempotent receipt application.
- Modify `backend/identity/repository.py`, `backend/decisions/repository.py`, and `backend/evaluation_v2/repository.py`: attach canonical workflow transitions/events through one shared transition helper without changing their tenant checks.
- Modify `backend/api.py`, `backend/routers/identity.py`, `backend/routers/decisions.py`, and `backend/routers/evaluations.py`: expose rollout/authority status and route activated-tenant mutations through the guard.
- Create `backend/routers/authority.py`: authenticated rollout status, activate, rollback, and projection replay endpoints.
- Create `backend/tests/authority/test_authority_models.py`, `test_authority_repository.py`, `test_authority_service.py`, `test_authority_projection.py`, `test_authority_endpoints.py`, and `test_authority_postgres.py`.
- Create `backend/tests/authority/test_authority_migration.py`: static migration/RLS/grant checks.
- Create `app-front-end/src/api/authority.ts`, `app-front-end/src/hooks/useAuthority.ts`, and corresponding Vitest tests; do not add direct `fetch` outside `src/api`.
- Modify `docs/institutional-foundation/phase-3-8-readiness.md` with authority migration and rollback evidence.

---

### Task 1: Add the tenant rollout and canonical workflow schema

**Files:**
- Create: `supabase/migrations/20260722090000_authority_control.sql`
- Create: `backend/authority/models.py`
- Test: `backend/tests/authority/test_authority_migration.py`, `backend/tests/authority/test_authority_models.py`

**Interfaces:**
- Produces `RolloutMode`, `WorkflowState`, `BlockCode`, `RolloutRecord`, `WorkflowStateRecord`, `WorkflowTransition`, and `ProjectionReceipt`.
- Produces tables `tenant_authority_rollouts`, `authority_projection_receipts`, and columns on `opportunities`: `workflow_state`, `workflow_version`, `block_code`, `block_detail`, `block_recovery`, `last_transition_id`.

- [ ] **Step 1: Write failing schema/model tests.** Assert the migration contains all five modes, legal mode transition metadata, `workflow_state` values, `workflow_version` optimistic-locking field, receipt uniqueness on `(user_id,event_id,consumer)`, service-role-only grants, and RLS. Assert Pydantic rejects an invalid tenant, mode, workflow state, or block record without recovery detail.

```python
def test_rollout_modes_and_workflow_states_are_closed_sets():
    assert [m.value for m in RolloutMode] == [
        "legacy", "shadow", "backfill", "canonical_write", "canonical_read"
    ]
    assert WorkflowState("triage_pending")
    with pytest.raises(ValueError):
        WorkflowState("invested")

def test_blocked_workflow_requires_code_detail_and_recovery():
    with pytest.raises(ValidationError):
        WorkflowTransition(user_id="tenant-a", state="blocked", expected_version=1)
```

- [ ] **Step 2: Run the tests and verify RED.**

Run: `pytest -q backend/tests/authority/test_authority_migration.py backend/tests/authority/test_authority_models.py`

Expected: collection/import failures because the authority package and migration do not exist.

- [ ] **Step 3: Add the migration and strict models.** The migration must:
  - add the workflow columns with a backfill default of `admitted`, then remove the default so new rows must choose a state;
  - create `tenant_authority_rollouts(user_id primary key, mode, version, activated_at, activated_by, snapshot_id, last_reconciliation_status, kill_switch, created_at, updated_at)`;
  - create `authority_projection_receipts(receipt_id, user_id, event_id, consumer, aggregate_type, aggregate_id, applied_at, projection_hash)` with a unique tenant/event/consumer key;
  - add a check that `workflow_state='blocked'` has a non-null `block_code`, `block_detail`, and `block_recovery`;
  - enable RLS, revoke `anon`/`authenticated`, and grant only `service_role` CRUD/execute;
  - add indexes for tenant/mode and tenant/workflow state.

```python
class RolloutMode(str, Enum):
    LEGACY = "legacy"
    SHADOW = "shadow"
    BACKFILL = "backfill"
    CANONICAL_WRITE = "canonical_write"
    CANONICAL_READ = "canonical_read"

class WorkflowState(str, Enum):
    ADMITTED = "admitted"
    IDENTITY_REVIEW = "identity_review"
    TRIAGE_PENDING = "triage_pending"
    TRIAGED_LIGHT = "triaged_light"
    DEEP_REVIEW_PENDING = "deep_review_pending"
    EVIDENCE_ACTIVE = "evidence_active"
    EVALUATION_PENDING = "evaluation_pending"
    RULING_PENDING = "ruling_pending"
    MONITORING = "monitoring"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    ARCHIVED = "archived"
```

- [ ] **Step 4: Run the tests and verify GREEN.**

Run: `pytest -q backend/tests/authority/test_authority_migration.py backend/tests/authority/test_authority_models.py`

Expected: all static/model tests pass; target-PostgreSQL tests remain skipped only when `TEST_DATABASE_URL` is absent.

- [ ] **Step 5: Commit.**

```bash
git add supabase/migrations/20260722090000_authority_control.sql backend/authority/models.py backend/tests/authority/test_authority_migration.py backend/tests/authority/test_authority_models.py
git commit -m "feat: add tenant authority rollout schema"
```

### Task 2: Implement transactional rollout and workflow authority

**Files:**
- Create: `backend/authority/repository.py`
- Create: `backend/authority/service.py`
- Test: `backend/tests/authority/test_authority_repository.py`, `backend/tests/authority/test_authority_service.py`, `backend/tests/authority/test_authority_postgres.py`

**Interfaces:**
- `AuthorityRepository.get_rollout(*, user_id) -> RolloutRecord` bootstraps `legacy` exactly once for a tenant.
- `AuthorityRepository.transition_rollout(*, user_id, expected_version, target_mode, actor_id, snapshot_id) -> RolloutRecord` uses `FOR UPDATE`, validates the legal next mode, increments `version`, and inserts an outbox event in the same transaction.
- `AuthorityRepository.transition_workflow(*, user_id, opportunity_id, expected_version, target_state, transition_id, block=None) -> WorkflowStateRecord` performs conditional update `where workflow_version=$expected_version` and emits `opportunity.workflow_changed` in the same transaction.
- `AuthorityService.authority(*, user_id) -> AuthorityContext` returns mode, version, kill-switch, and whether canonical writes/reads are permitted.
- `AuthorityService.require_write_path(*, user_id, operation) -> AuthorityContext` raises a typed `AuthorityBlocked` for canonical-read-only or killed tenants and returns legacy/shadow behavior explicitly.
- `AuthorityService.rollback(*, user_id, expected_version, actor_id, reason) -> RolloutRecord` transitions canonical modes back to legacy, sets kill-switch, and emits `authority.rollback_requested`.

- [ ] **Step 1: Write failing repository tests.** Cover bootstrap idempotency, illegal `legacy -> canonical_write`, legal ordered transitions, stale rollout version rejection, cross-tenant rejection, workflow optimistic-lock conflict, blocked-state validation, and event atomicity (forced outbox error rolls back the state change).

```python
async def test_stale_rollout_transition_is_rejected(pool):
    repo = AuthorityRepository(pool)
    current = await repo.get_rollout(user_id="tenant-a")
    with pytest.raises(AuthorityConflict):
        await repo.transition_rollout(
            user_id="tenant-a", expected_version=current.version - 1,
            target_mode=RolloutMode.SHADOW, actor_id="operator-a", snapshot_id=None,
        )
```

- [ ] **Step 2: Run RED.**

Run: `pytest -q backend/tests/authority/test_authority_repository.py backend/tests/authority/test_authority_service.py`

Expected: missing repository/service symbols or failing transition assertions.

- [ ] **Step 3: Implement repository transactions and service guards.** Use the existing `DecisionRepository._outbox` SQL shape and `require_user_id`; never select a rollout or opportunity without `user_id`. The legal transition map must be a closed dictionary:

```python
LEGAL_ROLLOUT_TRANSITIONS = {
    RolloutMode.LEGACY: {RolloutMode.SHADOW},
    RolloutMode.SHADOW: {RolloutMode.BACKFILL, RolloutMode.LEGACY},
    RolloutMode.BACKFILL: {RolloutMode.CANONICAL_WRITE, RolloutMode.SHADOW, RolloutMode.LEGACY},
    RolloutMode.CANONICAL_WRITE: {RolloutMode.CANONICAL_READ, RolloutMode.BACKFILL, RolloutMode.LEGACY},
    RolloutMode.CANONICAL_READ: {RolloutMode.CANONICAL_WRITE, RolloutMode.LEGACY},
}
```

`transition_workflow` must reject a human ruling or worker write when `kill_switch=true`, and must never derive a ruling from `workflow_state`. `AuthorityContext` must expose `canonical_writes_allowed`, `canonical_reads_allowed`, and `legacy_projection_allowed` as calculated booleans.

- [ ] **Step 4: Run GREEN and target-DB tests.**

Run: `pytest -q backend/tests/authority/test_authority_repository.py backend/tests/authority/test_authority_service.py backend/tests/authority/test_authority_postgres.py -rs`

Expected: unit/contract tests pass; PostgreSQL tests are skipped only without `TEST_DATABASE_URL` and validate real transaction rollback, RLS, unique receipt, and optimistic-lock behavior when configured.

- [ ] **Step 5: Commit.**

```bash
git add backend/authority/repository.py backend/authority/service.py backend/tests/authority/test_authority_repository.py backend/tests/authority/test_authority_service.py backend/tests/authority/test_authority_postgres.py
git commit -m "feat: enforce tenant authority and workflow transitions"
```

### Task 3: Build the one-way compatibility projector and receipts

**Files:**
- Create: `backend/authority/projection.py`
- Modify: `backend/jobs/outbox.py`
- Modify: `backend/identity/projection.py`
- Test: `backend/tests/authority/test_authority_projection.py`, `backend/tests/jobs/test_outbox_publisher.py`

**Interfaces:**
- `legacy_patch_for_event(event_type, payload) -> LegacyProjectionPatch` is a pure mapping for identity, evaluation, recommendation, ruling, memo, and workflow events.
- `AuthorityProjectionConsumer.apply(*, user_id, event_id, aggregate_type, aggregate_id, event_type, payload) -> ProjectionReceipt` claims `(user_id,event_id,"startups_compatibility")`, applies only the legacy startup patch, and returns the existing receipt on replay.
- `AuthorityProjectionConsumer.replay(*, user_id, event_id=None, opportunity_id=None) -> int` replays one event or all pending events for a tenant.

- [ ] **Step 1: Write failing projection tests.** Assert ADVANCE does not create a portfolio position, INSUFFICIENT_EVIDENCE is visible and never PASS, human ruling maps to `human_resolution`, canonical IDs/reasons are included, the second application is a no-op, a cross-tenant event is rejected, and a projector exception leaves an unpublished/retryable outbox row.

```python
def test_projection_is_idempotent_and_never_writes_canonical_tables(projector, legacy_repo):
    event = event_for("recommendation.created", user_id="tenant-a", payload={"state": "insufficient_evidence"})
    first = await projector.apply(**event)
    second = await projector.apply(**event)
    assert first.receipt_id == second.receipt_id
    assert legacy_repo.patch["partner_info"]["recommendation"] == "REVIEW"
    assert legacy_repo.canonical_writes == []
```

- [ ] **Step 2: Run RED.**

Run: `pytest -q backend/tests/authority/test_authority_projection.py backend/tests/jobs/test_outbox_publisher.py`

Expected: missing projector/receipt symbols and missing event mappings.

- [ ] **Step 3: Implement pure mappings and receipt-first application.** The projector must validate tenant IDs, claim the receipt in the same transaction as its legacy patch, and use the existing service-role startup storage only for display fields. It must never update `opportunities.current_*` pointers or insert a canonical ruling/evaluation. Extend `OutboxPublisher` with a consumer registry so authority events are projected while unrelated policy projection behavior remains unchanged.

- [ ] **Step 4: Run GREEN and replay tests.**

Run: `pytest -q backend/tests/authority/test_authority_projection.py backend/tests/jobs/test_outbox_publisher.py`

Expected: all mapping/idempotency/replay tests pass.

- [ ] **Step 5: Commit.**

```bash
git add backend/authority/projection.py backend/jobs/outbox.py backend/identity/projection.py backend/tests/authority/test_authority_projection.py backend/tests/jobs/test_outbox_publisher.py
git commit -m "feat: add idempotent canonical compatibility projection"
```

### Task 4: Route canonical writes and expose rollout controls

**Files:**
- Create: `backend/routers/authority.py`
- Modify: `backend/api.py`, `backend/routers/identity.py`, `backend/routers/decisions.py`, `backend/routers/evaluations.py`, `backend/identity/repository.py`, `backend/decisions/repository.py`, `backend/evaluation_v2/repository.py`
- Test: `backend/tests/authority/test_authority_endpoints.py`, existing identity/decision/evaluation endpoint tests

**Interfaces:**
- `GET /api/authority/status` returns `{mode, version, kill_switch, canonical_writes_allowed, canonical_reads_allowed, last_reconciliation_status}`.
- `POST /api/authority/transition` accepts `{target_mode, expected_version, snapshot_id}` and returns the new rollout record; only an authenticated operator identity may call it.
- `POST /api/authority/rollback` accepts `{expected_version, reason}` and returns a killed/legacy rollout record.
- `POST /api/authority/replay-projection` accepts `{event_id|opportunity_id}` and returns an applied count.
- `AuthorityService.require_write_path` is called before identity linkage, evaluation creation, recommendation creation, and human ruling creation. Legacy mode keeps existing behavior; shadow mode writes canonical records but does not change legacy outcomes; canonical_write projects canonical results; canonical_read routes reads to canonical DTOs.

- [ ] **Step 1: Write failing endpoint/route tests.** Cover auth/tenant scoping, status shape, illegal transition 409, stale expected version 409, rollback kill-switch, legacy mode compatibility, shadow non-interference, canonical-write projection enqueue, and canonical-read refusal when reconciliation status is not green.

- [ ] **Step 2: Run RED.**

Run: `pytest -q backend/tests/authority/test_authority_endpoints.py backend/tests/identity/test_identity_endpoints.py backend/tests/decisions/test_decision_service.py backend/tests/evaluation_v2/test_evaluation_endpoints.py`

Expected: missing routes/guards and failing mode assertions.

- [ ] **Step 3: Implement route guards and endpoint wiring.** Reuse `verify_clerk_token`/`request.state.user_id`; never accept a user ID from the request body as authority. Instantiate repositories with the authenticated tenant context. For canonical-write/read, reject direct legacy startup writes with a typed 409 containing `AUTHORITY_CANONICAL_ONLY`; for legacy/shadow preserve existing response schemas and attach authority metadata.

- [ ] **Step 4: Run GREEN and frontend contract tests.**

Run: `pytest -q backend/tests/authority/test_authority_endpoints.py backend/tests/identity/test_identity_endpoints.py backend/tests/decisions/test_decision_service.py backend/tests/evaluation_v2/test_evaluation_endpoints.py`

Expected: backend routes pass with no tenant leakage. Then add and run `npm test -- --runInBand src/api/authority.test.ts src/hooks/useAuthority.test.ts` from `app-front-end`.

- [ ] **Step 5: Commit.**

```bash
git add backend/routers/authority.py backend/api.py backend/routers/identity.py backend/routers/decisions.py backend/routers/evaluations.py backend/identity/repository.py backend/decisions/repository.py backend/evaluation_v2/repository.py backend/tests/authority/test_authority_endpoints.py app-front-end/src/api/authority.ts app-front-end/src/hooks/useAuthority.ts app-front-end/src/api/authority.test.ts app-front-end/src/hooks/useAuthority.test.ts
git commit -m "feat: route canonical writes through tenant authority"
```

### Task 5: Add frontend authority status and certification evidence

**Files:**
- Create: `app-front-end/src/api/authority.ts`
- Create: `app-front-end/src/hooks/useAuthority.ts`
- Modify: `app-front-end/src/App.tsx`, `app-front-end/src/hooks/useSystemData.ts`
- Test: `app-front-end/src/api/authority.test.ts`, `app-front-end/src/hooks/useAuthority.test.ts`, `backend/tests/authority/test_authority_certification.py`
- Modify: `docs/institutional-foundation/phase-3-8-readiness.md`

**Interfaces:**
- `getAuthorityStatus(): Promise<AuthorityStatus>` calls the authenticated API client.
- `transitionAuthority(input): Promise<RolloutRecord>` and `rollbackAuthority(input): Promise<RolloutRecord>` invalidate authority/status/opportunity queries on success.
- `useAuthority()` returns `{status, isCanonicalRead, isCanonicalWrite, blockedReason, refetch}` and never infers authority from legacy startup status.

- [ ] **Step 1: Write failing frontend/certification tests.** Assert canonical-read hides no data when an opportunity is blocked, displays rollout mode and recovery detail, invalidates query state after rollback, and cannot transition without expected version. Backend certification must cover authenticated manual lookup in legacy/shadow mode and canonical-write projection event receipt.

- [ ] **Step 2: Run RED.**

Run: `cd app-front-end && npm test -- --runInBand src/api/authority.test.ts src/hooks/useAuthority.test.ts`; `pytest -q backend/tests/authority/test_authority_certification.py`

Expected: missing client/hook/certification symbols.

- [ ] **Step 3: Implement typed client/hook and certification fixtures.** All requests use `api/auth.ts` token handling and TanStack Query; no direct component `fetch`. Render explicit blocked/rollback state and preserve the legacy queue until canonical-read status is true.

- [ ] **Step 4: Run the complete authority slice.**

Run: `pytest -q backend/tests/authority backend/tests/identity backend/tests/decisions backend/tests/evaluation_v2 -rs`; `cd app-front-end && npm test -- --runInBand && npm run lint && npm run build`; `python backend/scripts/check_phase8_readiness.py --json`.

Expected: all unit/contract tests pass, target-Postgres cases are skipped only without DSN, frontend test/lint/build pass, and readiness explicitly reports the authority migration/RLS checks and missing-DSN limitation.

- [ ] **Step 5: Commit docs and evidence.**

```bash
git add app-front-end/src/App.tsx app-front-end/src/hooks/useSystemData.ts app-front-end/src/api/authority.ts app-front-end/src/hooks/useAuthority.ts app-front-end/src/api/authority.test.ts app-front-end/src/hooks/useAuthority.test.ts backend/tests/authority/test_authority_certification.py docs/institutional-foundation/phase-3-8-readiness.md
git commit -m "docs: certify authority control rollout slice"
```

## Self-Review

- Spec coverage: Tasks 1–2 implement rollout/workflow state and fencing; Task 3 implements transactional outbox projection and receipts; Task 4 routes writes and rollback; Task 5 exposes frontend state and certifies the slice. Manual lookup/evidence/evaluation/recommendation/portfolio, historical backfill, triage, agent redesign, canonical reads, and remaining workflows are intentionally later slices from the approved design.
- Placeholder scan: no TODO/TBD or unspecified “handle edge cases” steps are used; each task has concrete files, interfaces, commands, expected outcomes, and commit boundaries.
- Type consistency: `RolloutRecord`, `WorkflowStateRecord`, `AuthorityContext`, `ProjectionReceipt`, and `LegacyProjectionPatch` are introduced in Task 1/2 and consumed by later tasks with the exact names above.

