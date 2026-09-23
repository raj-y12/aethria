# Current pipeline provenance

## Source-verified execution map

- Periodic discovery: `api._user_agent_loop` enqueues `PIPELINE_CYCLE` when
  `_durable_jobs_required()` (DATABASE_URL or compatibility storage switch).
  `jobs.handlers.pipeline_cycle_handler` calls `run_one_pipeline_cycle`.
  The CLI `run_system.py` and local API worker call that same runner directly.
  Active thesis, published policy, identity, authority, stage-enable settings,
  budget and ownership gates remain in force. Order: Scout → reference pruning
  → identity admission/claim ingestion → canonical evaluation → Reviewer → Partner.
- Main manual lookup: `/api/startups/lookup` dispatches durable COMPANY_LOOKUP
  or the local lookup queue. Both reach `run_on_demand_lookup`. Durable handlers
  admit identity first and resume the prior Scout checkpoint on retry. Runner
  order: Scout/reused startup → identity/claims → canonical evaluation → optional
  gap retrieval and post-extraction evaluation → Reviewer → Partner.
- `/api/startups/{startup_id}/rerun` uses the same dispatcher with
  `replace_startup_id`; it is not a fresh independent pipeline implementation.
- Thesis reprocessing runs Reviewer and Partner for eligible existing startups.
  No dedicated public Partner-only rerun route was found; PartnerEngine supports
  direct `run_startup` and `run_cycle` callers.
- `/api/opportunities/manual-lookup` is a distinct bound router. With a Postgres
  pool, API startup constructs OpportunityPipeline: identity → prerequisites →
  triage (may stop) → evidence/claims → evaluation → EvidenceReviewer →
  DeterministicPartner. Submitted claims are operator-asserted and references
  unverified, regardless of client trust flags. This is not ScoutEngine.
- Without the durable runtime, that canonical route returns unavailable. Local
  queues do not supply a canonical Postgres store; named prerequisite/Partner
  blocks can therefore prevent completion. They are not a scoring fallback.
- Authority rollout modes gate legacy writes and canonical reads. They do not
  make the old Partner threshold ladder active: `PartnerDecisionEngine.decide`
  returns through canonical mapping for both absent and present canonical input.

## Score and recommendation authority

Canonical `evaluation_v2` criteria are the active memo score authority. Legacy
Reviewer numeric fields remain historical data; Partner's old threshold code is
still present but unreachable through `decide`. A missing canonical recommendation
maps through insufficient evidence. DeterministicPartner routes the evaluator's
recommendation without choosing a new one. PartnerEngine additionally applies
its existing contradiction guard. Compatibility projections map canonical
states into legacy labels. Human rulings are separate from recommendations.

The Flow/memo may combine independently fetched current evaluation and startup
state. Run identity must be compared before assuming they are one review.
Technical metadata belongs in typed API data and development tooling; the normal
analyst experience remains evidence, reasoning, limitations, confidence and ruling.

## Inspect a displayed score

In a Vite development build, open Flow, select a startup and expand
**Development provenance** below the memo masthead. The inspector does not fetch
anything new: it observes the startup DTO, evaluation, current evidence ledger
and decision brief already loaded for that memo. It is compiled out of production
rendering and never participates in score selection.

- `memo.dimensions`: canonical score, full criterion reasoning, support and
  contradiction IDs, missing evidence, quality flags and legacy differences.
- `memo.overall_score`: the displayed compatibility mean of the scored Market,
  Product, Technical and Execution dimensions; Defensibility is excluded.
  `calculated_overall_score` remains inspectable when the scorecard blocks display.
  Confidence is the mean of non-null confidence for scored driver dimensions.
- `evaluation_provenance`: immutable evaluation/policy/snapshot identity, captured
  artifact → evidence item → claim links and per-claim eligibility/cap reasons.
- `lineage`: Scout/Reviewer/Partner run IDs and whether Partner's recorded
  evaluation matches the currently fetched evaluation. A null comparison means
  insufficient recorded identity, not a match.
- `compatibility`: stored legacy score values (normally suppressed in the
  analyst DTO), projected Partner recommendation, frontend mapping and human
  override. Matching values alone do not establish shared lineage.
- `agent_trace.evaluation_manifest`: existing exact execution/reuse identities,
  model identities, prompt versions and the immutable policy dependency manifest.

Flow queue scores are currently unavailable (`getQueueConvictionPct` returns
null). Queue recommendation first uses the existing human resolution, then Partner.
The memo decision brief instead combines evidence readiness, authoritative human
ruling and canonical machine lean. Its thesis-alignment number still comes from
Reviewer (`<=1` is displayed on a ten-point scale). These are different signals.

The canonical-read frontend adapter currently maps `pass` to `PASS` and **all
other canonical states**, including `advance`, to `MONITOR`; its Scout confidence
is a compatibility placeholder. Phase 0 records this existing mapping explicitly
and does not correct it. Legacy Partner threshold code exists but public `decide`
cannot reach it. Historical Reviewer values therefore remain `UNKNOWN_LEGACY`
unless a recorded source explains them; they are not relabeled canonical.

## Storage and lifecycle

`evaluation_runs.model_manifest.pipeline_provenance` stores a server-supplied
binding plus source links/eligibility. `claim_snapshot` and its hash are unchanged.
Source Scout lineage is read through a tenant-scoped join to the linked startup
inside the same repeatable-read evaluation transaction. Reruns can therefore
retain a source Scout run from an earlier pipeline run. No backfill is performed.

New completed `agent_trace` stages have distinct invocation UUIDs, available prompt
identity and source metadata. Reviewer trace lists canonical context claim IDs;
Reviewer analysis is not falsely described as having been computed by the
canonical evaluator. Partner persists the exact evaluation ID/hash passed to the
invocation, original canonical recommendation, mapped recommendation, final result
and whether policy, contradiction guarding or JSON validation changed that result.
Deterministic routing has no executed model ID.

Use existing job IDs/pipeline IDs to correlate `agent_job_checkpoints`, stage
outcome metadata and pipeline logs. Attempts remain explicit on checkpoints;
retry starts are logged as `RETRIED`. The runner logs starts and terminal stage
outcomes, and lookup evaluation checkpoints include the exact evaluation/snapshot.
The separate OpportunityPipeline returns its observed ordered stage trace,
including identity blocks and triage evaluation skips. No new observability
service, endpoint, permission or database table is introduced.

## Frozen baseline cases

`backend/tests/evaluation_v2/phase0_golden_pipeline.json` freezes evidence and full
criterion/recommendation outputs under pinned v4 Partner rules and v3 rubric.
Tests never regenerate the fixture or contact external providers. These are
historical outputs, not the current authority. `historical_fixtures.py` retains
the inputs; `tests/investment_analysis/test_baseline_comparison.py` checks current
analysis against those companies. The historical evaluator is no longer executed.

| Case | Historical canonical output | Historical Partner output |
|---|---|---|
| Strong verified | Dimensions 8, advance | INVEST |
| Strong-looking, unverified | Null scores, insufficient evidence | MONITOR |
| Contradictory | Score may remain 8; recommendation insufficient evidence | MONITOR |
| Missing dimension | Missing execution null, insufficient evidence | MONITOR |
| Outside mandate | Advance | MONITOR with mandate hold |
| Legacy/canonical divergence | Legacy 9, canonical 6, monitor | MONITOR |
| No evidence | Null scores, insufficient evidence | MONITOR and human review |

The 6 is the existing inclusive monitor boundary. The contradictory 8 is not an
instrumentation defect: criterion scoring and recommendation sufficiency are
separate current behaviors. Legacy handoff values are frozen fixtures, not claims
that the retired threshold ladder ran.

## Verification scope and remaining limits

The component integration test runs real snapshot evaluation, EvaluationRepository,
PartnerEngine persistence and the authenticated API projection against a SQL
transport double; Reviewer model output is frozen. The PostgreSQL contract test
uses real evidence ingestion, claim creation, evaluation persistence, round-trip
projection and cross-tenant rejection, with all synthetic writes rolled back.
The CI Postgres job includes it. Stage and frontend tests cover immutable inputs,
null history, preserved analyst score suppression, legacy divergence, mismatched
evaluation identities and production inspector gating.

This is not a live Exa/Firecrawl/OpenAI or full durable-worker acceptance run.
The existing screenshot harness exercises real Flow/memo components with sample
data but lacks canonical evaluation responses; it verifies the inspector's
unavailable-data state, not a live scored company. Golden/component tests cover
the scored cases. No production credentials, tenant data or model calls are needed.

Existing gaps relevant to later migration remain visible:

- Historical missing stage IDs/models/prompt versions stay null. A current evidence
  ledger must not be mistaken for the immutable evidence snapshot.
- Current startup stage traces are last-stage projections; durable checkpoints and
  logs carry run/attempt history. This does not add an all-history run-ID resolver.
- An evaluation identifies its bound Scout state and snapshot; merged evidence can
  include multiple source observations. Artifact source observation IDs preserve
  that distinction rather than claiming one Scout authored all evidence.
- Reviewer narrative is not a canonical score input. Its context claim IDs and
  stage/run identity are recorded separately; there is no invented one-to-one
  Reviewer/evaluation relationship.
- Unrecorded evidence-plan IDs, score schema versions and Reviewer rule versions
  remain null rather than being filled from current configuration.
- Portable-table RLS coverage remains the pre-existing documented gap. New reads
  and joins remain tenant-scoped; no access was broadened.

Phase 0 changes neither scores nor recommendation authority. It supplies a
baseline for reviewing later contracts, but a live deployment acceptance run and
an agreed policy for historical lineage completeness remain prerequisites to
claiming exhaustive production traceability. Phase 1 is not implemented here.

## Verification record (Phase 0)

- Root `python3 -m pytest -o asyncio_mode=auto`: **2453 passed, 24 skipped,
  1 warning** (17.23s). The warning is the existing Starlette/httpx deprecation.
- Isolated PostgreSQL 16 with all 31 existing migrations applied:
  `TEST_DATABASE_URL=… python3 -m pytest backend/tests/evaluation_v2/test_phase0_provenance_postgres.py backend/tests/jobs/test_job_repository_postgres.py backend/tests/startup/test_repository_postgres.py -q -o asyncio_mode=auto`:
  **18 passed**. The provenance test was then extended to exercise the real
  OpportunityPipeline with frozen identity admission, real evidence/evaluation
  adapters, deterministic Partner and authenticated API projection; its rerun
  **passed**. The temporary database was removed after verification.
- App `npm run lint`, `npm test -- --maxWorkers=1 --minWorkers=1`,
  `npm run build`, `npm run check:bundle`: passing; full suite **99 files,
  512 tests**. Single-worker execution avoids transient local ENOSPC failures.
  The build also caught and corrected nullable legacy score DTO types to match
  existing API suppression. The demo build retains its chunk-size warning.
- Web `npm run lint && npm run build && npm run check:bundle && npm run check:marketing`:
  passing, **52 assets**, **17 marketing checks**.
- `git diff --check`: passing. Graphify refreshed successfully (ignored output).
- Manual development harness: Flow → startup → Development provenance expanded;
  unavailable canonical data remains explicit. No live provider acceptance run.
- Local Python is 3.13; CI targets 3.12. Database tests need TEST_DATABASE_URL and
  otherwise skip; CI now explicitly runs the new contract test in its PG job.

No score, recommendation, prompt, policy or decision-authority change is intended
or observed in the frozen comparisons. No migration or historical backfill was
performed. Pre-existing HomePage.tsx and HomePage.test.tsx changes were preserved.

## File inventory

Paths below are repository-relative. Each entry is part of Phase 0, except the
explicitly excluded pre-existing HomePage changes above.

| File | Reason |
|---|---|
| `.github/workflows/ci.yml` | Run new provenance Postgres contract in CI. |
| `API.md` | Document additive internal provenance DTO fields. |
| `backend/.gitignore` | Allow the deterministic golden JSON fixture. |
| `backend/agent_trace.py` | Record stage IDs, known versions and stage lineage. |
| `backend/api.py` | Expose internal projection metadata alongside unchanged analyst fields. |
| `backend/compatibility_projection.py` | Describe stored legacy scores before normal suppression. |
| `backend/evaluation_v2/provenance.py` (new) | Typed tenant-checked evaluation and evidence provenance. |
| `backend/evaluation_v2/evidence_projection.py` | Include artifact/source references in the audit projection. |
| `backend/investment_analysis/repository.py` | Freeze pipeline/evidence bindings in existing manifests and return provenance. |
| `backend/jobs/handlers.py` | Record checkpoint/retry lifecycle using existing pipeline logging. |
| `backend/models.py` | Add optional typed Partner provenance. |
| `backend/opportunity_pipeline.py` | Trace current stage order and bind evaluations to pipeline runs. |
| `backend/investment_analysis/projection.py` | Project current judgment/action provenance; the historical Partner engine has been removed. |
| `backend/pipeline_runner.py` | Bind current runner/evaluation/stage lineage and checkpoints. |
| `backend/pipeline_state.py` | Extend lifecycle logging states. |
| `backend/tests/test_phase0_stage_provenance.py` (new) | Protect run identities, unchanged decisions and API suppression. |
| `backend/tests/evaluation_v2/phase0_golden_pipeline.json` (new) | Freeze seven current evidence/score/decision cases. |
| `backend/tests/evaluation_v2/historical_fixtures.py` | Preserve frozen inputs without historical execution. |
| `backend/tests/evaluation_v2/test_phase0_provenance_e2e.py` (new) | Walk evaluator, frozen Reviewer, actual Partner and API; test tenant boundaries. |
| `backend/tests/evaluation_v2/test_phase0_provenance_postgres.py` (new) | Verify real storage, pipeline, provenance round trips and tenant isolation. |
| `backend/tests/identity/test_autonomous_identity_admission.py` | Assert added evaluation binding. |
| `backend/tests/opportunity_pipeline/test_manual_lookup_pipeline.py` | Assert actual trace order and binding. |
| `app-front-end/src/api/evaluations.ts` | Type additive evaluation provenance. |
| `app-front-end/src/api/startups.ts` | Describe existing canonical-to-legacy adapter mapping. |
| `app-front-end/src/types/startup.ts` | Type internal projection metadata and existing nullable legacy scores. |
| `app-front-end/src/lib/pipelineProvenance.ts` (new) | Build audit report from data the memo actually renders. |
| `app-front-end/src/lib/__tests__/pipelineProvenance.test.ts` (new) | Protect score origins, divergence, overrides and stale evaluation detection. |
| `app-front-end/src/components/memo/PipelineProvenanceInspector.tsx` (new) | Collapsed development-only inspector. |
| `app-front-end/src/components/memo/__tests__/PipelineProvenanceInspector.test.tsx` (new) | Verify debug visibility and production hiding. |
| `app-front-end/src/components/InvestmentMemoContent.tsx` | Attach inspector to existing memo data. |
| `app-front-end/src/lib/canonicalScoring.ts` | Correct stale comment about legacy fallback; no logic change. |
| `docs/adr/0014-observability-does-not-change-decision-authority.md` (new) | Record authority-preserving instrumentation boundary. |
| `docs/adr/README.md` | Index ADR. |
| `docs/operations/pipeline-provenance.md` (new) | Execution map, inspection guide, limitations and verification evidence. |
