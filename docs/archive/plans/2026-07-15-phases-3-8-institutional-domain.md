# Phases 3–8 Institutional Domain Implementation Plan

> Execute inline on `codex/institutional-foundation`. Backend and migrations are in scope; frontend source remains unchanged and is handed off through the frontend impact ledger.

**Goal:** Complete the approved evidence-and-decision substrate beyond canonical identity: evidence, immutable evaluation, human rulings/actions, cost-aware monitoring, governed learning, and channel/outcome expansion.

**Architecture:** New normalized records remain tenant-scoped and append-oriented. Services use Pydantic contracts and asyncpg repositories. Existing startup/memo APIs remain compatibility projections. Automatic workers may retrieve, extract, recommend, draft, and propose; only authenticated operators may rule, approve external actions, or publish policy.

**Technology:** FastAPI, Pydantic v2, asyncpg/PostgreSQL/Supabase migrations, existing durable job/outbox substrate, pytest.

---

## Phase 3 — evidence and claims

1. Add artifact, evidence-item, claim, claim-link, and evidence-plan contracts and schema.
2. Implement transactional evidence repository with content-hash idempotency, immutable provenance, contradiction/staleness, and safe correction events.
3. Implement deterministic source trust/freshness classification and founder-claim standard; block unsupported personality labels and flag untrusted prompt-injection content.
4. Add evidence-ledger read and correction APIs with tenant isolation and private-artifact redaction.
5. Seed evidence plans from opportunity gaps and record refresh requests through the outbox.

## Phase 4 — immutable evaluation and recommendation

1. Add immutable evaluation-run, claim-snapshot, criterion-assessment, and recommendation schema/contracts.
2. Implement deterministic evaluation over canonical snapshot values and hashes.
3. Preserve prior successful recommendation when a refresh fails; supersede, never update, completed evaluations.
4. Add recommendation delta explanation and read APIs.
5. Add compatibility projection helpers for legacy recommendation vocabulary.

## Phase 5 — rulings and bounded workflow

1. Add append-only human rulings, override signals, and workflow actions.
2. Implement fast authenticated rulings with recommendation/ruling separation and typed override attribution.
3. Generate diligence questions and information-request drafts from explicit missing evidence.
4. Require explicit approval before CRM export or any external write; audit every transition.
5. Add ruling/action APIs and operator-safe read models.

## Phase 6 — attention-triggered enrichment

1. Add lifecycle service levels, next-review scheduling, budget reservations/settlement, and material-change records.
2. Implement cost-gated refresh planning and cheap snapshot-change detection.
3. Add durable evidence-refresh job type and handler checkpoints.
4. Ensure archived/passed records do not receive recurring enrichment without an explicit lifecycle reason.
5. Add monitoring/status APIs and bounded metrics.

## Phase 7 — Fund Intelligence

1. Add learning signals, policy proposals, impact previews, and versioned policy drafts.
2. Derive attributable override patterns with minimum sample thresholds and limitations.
3. Implement review/accept/reject/defer and separate explicit publish; no proposal may self-activate.
4. Preserve rejection/deferral memory and proposal evidence links.
5. Add Fund Intelligence APIs and governance tests.

## Phase 8 — channels and outcomes

1. Add bounded CSV/import candidate ingestion through SourceObservation and canonical identity.
2. Add verified outcome observations with evidence, dates, materiality, and a non-causal interpretation contract.
3. Reuse confidential artifact access/retention controls for future deck/email ingestion.
4. Add outcome/import APIs and tenant/security tests.
5. Extend the golden set and readiness/frontend ledgers through Phase 8.

## Verification and delivery

1. Run all focused institutional tests and existing security/lookup/pipeline compatibility suites.
2. Run the full backend test suite.
3. Run golden-set/readiness commands; report target-PostgreSQL skips or missing DSN honestly.
4. Audit every new public endpoint for authentication, tenant scoping, bounded pagination, safe errors, and no raw confidential content.
5. Produce a final exact frontend component/API update list ordered by correctness dependency.
