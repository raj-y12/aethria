# Internal pipeline contracts

Phase 1 establishes target schemas and reversible adapters. It does **not** switch
runtime consumers to them. Import target types from `pipeline_contracts.models`
and pure adapters from `pipeline_contracts.adapters`. Existing same-named
TypedDicts under scout/reviewer/partner remain unchanged and must be imported
explicitly to avoid confusion.

## Boundary and contracts

The Phase 0 execution map remains authoritative. Source inspection confirmed the
least disruptive boundary is standalone code, with no database migration or
new API fields. `models.ScoutInfo`, `ReviewInfo`, `PartnerInfo`, the three agent
schemas, `evaluation_v2.models`, `agents.canonical`, existing storage adapters,
backend compatibility projections, frontend evaluation DTOs and memo provenance
all retain their current behavior.

| Contract | Purpose |
|---|---|
| ScoutOutput | Identity, factual reasoning, unknowns, contradictions, sources and evidence summary; legacy hypotheses remain outside its core. |
| ReviewerInput | Scout factual/evidence context, evidence items, thesis/mandate/portfolio/analyst context and optional prior review. |
| ReviewerOutput | Assessments, composable sections, investment case, risks, unknowns, contradictions, diligence priorities and overall assessment. |
| ReviewerAssessment | Identified dimension conclusion, optional proposed score, rationale, confidence, support and reasoning units. |
| ReasoningUnit | Identified FACT/INFERENCE/ASSUMPTION/OPINION/UNKNOWN text with claim/evidence/source references. |
| AnalysisSection | Typed optional section with PRESENT/NOT_APPLICABLE/UNKNOWN/UNSUPPORTED/NOT_ASSESSED status. |
| ValidatedAssessment | Optional proposal reference, validated score, status, cap, coverage, support/contradictions, policy and evidence references. |
| AssessmentValidationResult | Tenant-scoped assessment collection, lineage, policy versions and human-review requirement. |
| PartnerInput | Identity, Reviewer output, validation, evidence/unknowns/contradictions, thesis/mandate/context, prior decision and overrides. |
| PartnerOutput | Decision, rationale, investment case, risks, next steps, conviction, policy result and assessment references. |
| Lineage / References / PolicyVersions / StageMetadata | Shared opaque identifiers and known execution/policy identity. |
| Identity / SourceReference / EvidenceItem / EvidenceSummary / ReviewContext / PolicyResult | Small reusable components. |
| LegacyExtension | Complete original JSON and explicit mapping limitations, isolated from target meaning. |

ScoreOrigin reuses Phase 0's enum. Recommendation origins, validation status,
reasoning types, review status and analysis sections are explicit enums. Named
identifier aliases share a nonempty opaque string representation. They validate
wire shape, not database existence or ownership.

## Adapters and mismatches

All adapters require keyword `user_id`, `payload`, and a `Lineage` constructed
from trusted server context. Payload may be a JSON mapping or existing Pydantic
model. PostgreSQL UUIDs/dates normalize to JSON strings. Nulls, absent keys, empty
lists, zero confidence, legacy fields and unknown extension keys survive replay.

| Adapter | Mapping and limitation |
|---|---|
| adapt_current_scout_to_scout_output | Scout identity, recorded unknown and source notes; narrative, hypotheses, estimates and unverified descriptions remain in compatibility. It creates no verified facts. |
| adapt_current_review_to_reviewer_output | Dimension reasoning, qualitative sections, thesis/risk/diligence narrative and metadata. Legacy numbers are preserved, never assigned to proposed_score. Unrecorded origin is UNKNOWN_LEGACY. |
| adapt_current_evaluation_to_validation_result | Pure EvaluationResult or repository DTO criteria become CURRENT_EVALUATION records. Existing score and criterion IDs survive; reviewer-assessment and validation-run references stay absent. |
| adapt_current_partner_to_partner_output | Existing INVEST/PASS/MONITOR is copied exactly, including zero confidence and known mapping/guard metadata. No threshold or fallback runs. |
| adapt_current_evidence_review | Alternate pipeline evaluation summary; no fabricated Reviewer assessments. |
| adapt_current_partner_route | Alternate canonical route remains a route in compatibility; target decision stays null. |
| project_current_payload | Exact captured JSON replay, suitable for handing back to the existing consumer/adapter. Target-only contracts without a captured payload are rejected. |

Current unclassified narrative becomes UNKNOWN reasoning, never an invented FACT
or INFERENCE. A context-wide claim list is not per-assessment support. Unsupported
future evaluation dimensions remain in original JSON rather than being relabeled.
Exact current sufficiency strings and per-claim cap adjustments also remain there;
this adapter does not infer an aggregate cap or rewrite validation semantics.
Missing sections are omitted; a present null/empty legacy section maps to UNKNOWN.
A future producer can explicitly emit NOT_APPLICABLE or NOT_ASSESSED.

The compatibility assessment/reasoning digest includes tenant, known lineage,
payload and field path. Repeated adaptation is deterministic; changed content or
lineage changes the projection ID. These IDs are not historical run IDs and are
not persisted. Caller-supplied current run IDs remain unchanged. No source IDs
are invented from URLs, and artifact IDs are not relabeled source IDs.

## Runtime and tenancy

Periodic, manual lookup, rerun, thesis reprocessing, durable jobs, local fallback,
and `/api/opportunities/manual-lookup` continue using the existing schemas and
adapters. The new adapters perform no I/O, prompt/model calls, scoring, storage,
queue changes or policy loading. Flow/memo reads and the Phase 0 development
inspector are unchanged; no raw metadata is added to analyst components.

Obtain data through existing tenant-scoped repositories first. Adapters require
explicit user context, reject conflicting embedded ownership and refuse
cross-tenant replay. Nested target envelopes reject mismatched tenant/company/
opportunity identities. They cannot prove ownership of an opaque ID without a
repository lookup and deliberately do not provide such a lookup.

## Phase 2 boundary

Scout can now be migrated behind these contracts, with existing data recoverable
through compatibility replay. Phase 2 still needs explicit factual field extraction
and evidence attribution rules. No legacy field may be dropped merely because it
has no core mapping. Persisted target IDs, validation authority and Partner
assessment links remain future decisions. Edited target outputs must not be saved
using snapshot replay; that would discard those edits by design.

No company knowledge-base behavior changed: this is an unused internal boundary
with frozen runtime semantics. Repository source and ADR-0015 document the design.

## Files changed in Phase 1

Pre-existing Phase 0 and HomePage working-tree changes are not part of this
inventory and were preserved. No commits, branches or migrations were created.

| File | Reason |
|---|---|
| `backend/pipeline_contracts/__init__.py` | Introduce an explicit internal package, separate from existing engine schemas. |
| `backend/pipeline_contracts/models.py` | Shared target contracts, enums, lineage and composition checks. |
| `backend/pipeline_contracts/adapters.py` | Six pure current-payload adapters and lossless replay projection. |
| `backend/tests/pipeline_contracts/test_adapters.py` | Deterministic mapping, serialization, tenant checks, lineage, exact replay and seven golden regressions. |
| `backend/tests/pipeline_contracts/test_postgres.py` | Reuse the existing rolled-back real pipeline harness to verify evaluation adapter replay. |
| `.github/workflows/ci.yml` | Add the new PostgreSQL adapter test to the existing database job; preserve Phase 0 addition. |
| `docs/adr/0015-internal-contracts-with-lossless-legacy-adapters.md` | Record opt-in contracts, replay semantics, identity strategy and authority boundary. |
| `docs/adr/README.md` | Index ADR-0015 while preserving ADR-0014. |
| `docs/operations/pipeline-contracts.md` | Contract/mapping reference, limitations, inventory and verification. |

## Verification

- Direct contract tests plus Phase 0 golden suite:
  `python3 -m pytest backend/tests/pipeline_contracts backend/tests/evaluation_v2/test_phase0_golden_pipeline.py -q -o asyncio_mode=auto`:
  **41 passed, 1 skipped** without a database configured. All seven frozen
  cases remain unchanged, including canonical 6 / legacy 9 / MONITOR.
- Full backend with database explicitly disabled:
  `TEST_DATABASE_URL='' python3 -m pytest -o asyncio_mode=auto`:
  **2433 passed, 79 skipped, 1 warning** (11.88s).
- Full backend against the explicitly configured isolated PostgreSQL database:
  `TEST_DATABASE_URL=<isolated-test-dsn> python3 -m pytest -o asyncio_mode=auto`:
  **2508 passed, 4 skipped, 1 warning** (14.36s).
- Isolated PostgreSQL 16, all 31 existing migrations applied: CI-listed
  PostgreSQL contracts plus startup repository contracts **52 passed** (2.46s).
  This includes the new adapter test, actual evidence/evaluation storage,
  deterministic manual pipeline, API projection and cross-tenant rejection.
- App: `npm run lint`, `npm test -- --maxWorkers=1 --minWorkers=1`,
  `npm run build`, `npm run check:bundle`: **passed**; **512 tests / 99 files**,
  **65 assets** within budget. No frontend source changes in Phase 1.
- Web: `npm run lint`, `npm run build`, `npm run check:bundle`,
  `npm run check:marketing`: **passed**; **52 assets**, **17 marketing checks**.
- `git diff --check`: passed. Graphify structural refresh completed with ignored
  generated output. No external retrieval or model calls were needed.

The backend warning is the existing Starlette/httpx TestClient deprecation;
local Python is 3.13 while CI targets 3.12. The demo build retains its existing
chunk-size warning. No golden fixture was regenerated or edited.
