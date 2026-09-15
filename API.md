# API Reference

FastAPI application: `backend/api.py`, with domain routers under
`backend/routers/`. Base URL is `http://localhost:8000` locally.

Interactive OpenAPI docs are served at `/docs` and `/openapi.json` — **disabled
in production** unless `PUBLIC_API_DOCS_ENABLED` is set.

---

## Conventions

**Authentication.** Every route except `GET /health` (and the doc routes)
requires `Authorization: Bearer <clerk_jwt>`. Verification is RS256 against the
Clerk JWKS endpoint and fails closed:

```
401 {"detail": "Missing or invalid authorization token"}
```

The verified `sub` claim becomes the tenant for the request. There is no way to
address another tenant's data.

**Common status codes.**

| Code | Meaning in this API |
|---|---|
| `200` | Success, or a deliberate no-op with a `status`/reason in the body |
| `202` | Work accepted onto the durable job store or worker queue |
| `401` | Missing/invalid token |
| `422` | Request body failed server-side validation |
| `429` | Rate-limit policy exceeded for this route class |
| `503` | A required dependency is unconfigured or unavailable (Supabase, durable job store, worker) |

**Rate limiting.** Lookup (per-minute and per-day), lookup resolve, agent
trigger, meta trigger, settings mutation, and the admin routes each have their
own fixed-window policy (`backend/security/rate_limiter.py`).

---

## Health, identity, and system

| Method | Path | Notes |
|---|---|---|
| `GET` | `/health` | Public liveness heartbeat |
| `GET` | `/metrics` | Process and pipeline counters |
| `GET` | `/api/me` | The authenticated `user_id` |
| `GET` | `/api/system/status` | Aggregate readiness snapshot for the UI |
| `GET` | `/api/stream` | **SSE.** Per-user event stream; emits a hello frame, then `startups_changed` and related nudges. Capped by `SSE_MAX_CONNECTIONS` (503 beyond), keepalive every `SSE_KEEPALIVE_SECONDS` |

## Startups and memo

| Method | Path | Notes |
|---|---|---|
| `GET` | `/api/startups` | Thin list projection for the deal grid. Bounded by `STARTUPS_LIST_DEFAULT_LIMIT` / `STARTUPS_LIST_MAX_LIMIT` |
| `GET` | `/api/startups/{startup_id}` | Full scout / review / partner payload |
| `GET` | `/api/startups/{startup_id}/memo` | Progressive memo: `{status: "ready"\|"generating"\|"failed", memo, partial: {scout, review, partner}, pipeline_run_id, error}` |
| `POST` | `/api/startups/{startup_id}/acknowledge` | Mark a deal as seen |
| `POST` | `/api/startups/{startup_id}/rerun` | Re-run review/decision for an existing deal |

## On-demand lookup

| Method | Path | Notes |
|---|---|---|
| `POST` | `/api/startups/lookup` | Body `{lookup_input, lookup_id?}`. Returns `202` with queued metadata and the resolved `lookup_id` |
| `GET` | `/api/startups/lookup-status?lookup_id=` | Status/outcome for a queued lookup, including recorded failures |
| `POST` | `/api/startups/lookup/resolve` | Choose among ambiguous candidates using a short-lived server-side resolution token |
| `POST` | `/api/startups/lookup/cancel` | Cancel an in-flight lookup |
| `POST` | `/api/opportunities/manual-lookup` | Canonical-path manual lookup through the identity → evidence → evaluation pipeline |

## Agents and pipeline control

| Method | Path | Notes |
|---|---|---|
| `POST` | `/api/agents/trigger` | Enqueue one pipeline cycle. `202` queued · `200` skipped (agents disabled, Supabase or thesis missing) · `503` worker/durable store unavailable |
| `GET` | `/api/agents/status` | Readiness diagnostics: worker state, Supabase/OpenAI config, thesis readiness |
| `POST` | `/api/agents/toggle` | Enable/disable the per-user agent loop |
| `GET` | `/api/agents/loop-status` | Current persistent-loop state for the tenant |

## Durable jobs

| Method | Path | Notes |
|---|---|---|
| `GET` | `/api/jobs` | Tenant-scoped job list: accepted / running / retry / blocked / final |
| `GET` | `/api/jobs/{job_id}` | Single job, including block code and attempt history |
| `POST` | `/api/jobs/{job_id}/retry` | Explicit recovery |
| `POST` | `/api/jobs/{job_id}/cancel` | Explicit cancellation |

## Canonical identity

| Method | Path | Notes |
|---|---|---|
| `GET` | `/api/companies/{company_id}` | Canonical company record |
| `GET` | `/api/opportunities` | Bounded opportunity list |
| `GET` | `/api/opportunities/{opportunity_id}` | Canonical opportunity record |
| `GET` | `/api/opportunities/{opportunity_id}/decision-view` | Composed decision-ready view |
| `GET` | `/api/opportunities/{opportunity_id}/decision-cases` | Historical decision-event collection: one case per completed evaluation, with its recommendation, criteria, linked rulings/overrides, Aethria-owned rationale interpretations, decision-time evidence snapshot, and separate later outcomes. Rulings without a recommendation link are returned as `unpaired_rulings`, never inferred into a case |
| `GET` | `/api/evaluations/{evaluation_id}/precedents` | Deterministically ranked, tenant-scoped comparable historical decision episodes with component scores, match reasons, limitations, and separate later-outcome context |
| `GET` | `/api/startups/{legacy_startup_id}/opportunity` | Legacy → canonical bridge |
| `GET` | `/api/observations` | Bounded source-observation queue |
| `GET` | `/api/identity-cases` | Open ambiguity queue |
| `POST` | `/api/identity-cases/{identity_case_id}/resolve` | Explicit match/create ruling |
| `POST` | `/api/identity-cases/{identity_case_id}/defer` | Defer without resolving |
| `POST` | `/api/identity-cases/{identity_case_id}/reject` | Reject the proposed match |

## Evidence

| Method | Path | Notes |
|---|---|---|
| `GET` | `/api/opportunities/{opportunity_id}/evidence` | Redacted artifact / claim / evidence ledger |
| `POST` | `/api/opportunities/{opportunity_id}/evidence-plans` | Create a bounded diligence plan |
| `POST` | `/api/opportunities/{opportunity_id}/confidential-evidence` | Register confidential evidence under an access class |
| `POST` | `/api/claims/{claim_id}/correct` | Append an operator correction (claims are never overwritten) |

## Evaluation and decisions

| Method | Path | Notes |
|---|---|---|
| `GET` | `/api/opportunities/{opportunity_id}/evaluation` | Current immutable evaluation + machine recommendation; incomplete, contradictory, malformed, or ungrounded decision evidence returns the existing `insufficient_evidence` state, never an authority ruling |
| `POST` | `/api/opportunities/{opportunity_id}/evaluate` | Explicit operator refresh; fails closed on unmet prerequisites |
| `POST` | `/api/opportunities/{opportunity_id}/rulings` | Record the authoritative human ruling |
| `GET` | `/api/opportunities/{opportunity_id}/rulings` | Ruling history |
| `POST` | `/api/rulings/{ruling_id}/interpretation-corrections` | Append an operator correction to the Aethria-owned ruling interpretation; raw rationale remains unchanged |
| `POST` | `/api/opportunities/{opportunity_id}/investment` | Record the investment transition |
| `GET`/`POST` | `/api/opportunities/{opportunity_id}/actions` | Workflow actions and drafts |
| `POST` | `/api/actions/{workflow_action_id}/approve` | Approval record — does **not** itself perform an external write |

### Internal provenance metadata

Current shared-analysis evaluations also carry typed internal contracts under
`evaluation.judgment_audit.investment_analysis`. Criterion
`deterministic_adjustments.assessment_validation` distinguishes proposed and
validated scores, cap reason, support and contradiction status. Score origins
add `REVIEWER_ASSESSMENT` and `VALIDATED_REVIEWER_ASSESSMENT`; recommendation
origin adds `PARTNER_ANALYSIS`. Historical records keep their original origins.
Normal scorecards display investment explanations only.
New immutable claim snapshots include optional linked `display_excerpt`,
`source_uri` and `artifact_id` fields. Historical snapshots without those fields
remain readable. The analysis audit records factual preparation and any bounded
targeted research, including the initial review when new evidence caused a
second Reviewer pass. Those source/run details remain internal; the analyst sees
the final rationale, evidence limitations and unresolved diligence.

Explicit evaluation refresh returns a named `{code, detail}` error for analysis
dependency changes (409), unconfigured models, unavailable model budgets or
failed factual preparation (`evidence_preparation_failed`, 503).
`POST /api/opportunities/{opportunity_id}/evaluate?scope=partner` reuses a completed
review only when its factual evidence and published review policy/thesis are
unchanged. It revalidates freshness and calls Partner alone. Incompatible or
missing prior reviews return 409 and require the default full refresh.
The existing startup `triage-override` action converges on this same evaluator:
`stage=review` refreshes the full analysis and `stage=decide` performs Partner-only
refresh. Neither action invokes the retired Reviewer persona scoring engine.
Scout projections add `unknowns` and `contradictions`; legacy hypothesis fields
remain readable but are not populated by factual Scout v2.

The current evaluation DTO has an additive `provenance` object (typed in
`backend/evaluation_v2/provenance.py` and `app-front-end/src/api/evaluations.ts`).
It binds the pipeline entry/run, source Scout run, company/opportunity,
evaluation ID, immutable evidence snapshot hash, evidence artifact/item/claim
links, rubric/policy/thesis versions and recommendation origin. Each criterion
retains its canonical score, support/contradiction IDs, quality flags and exact
recorded claim eligibility/caps. Missing historical metadata is null or an empty
collection; it is never reconstructed from today's policy.

Startup DTOs include additive `projection_provenance`: stored historical scores,
their recorded source (or `UNKNOWN_LEGACY`), compatibility IDs, Partner provenance
and human override. Normal `review.*_score` fields remain null. New stage trace
entries carry distinct Scout/Reviewer/Partner invocation IDs. Partner metadata
records the original canonical state, its mapping, policy/guard/validation changes
and the exact evaluation ID/hash supplied to that invocation when available.
The startup's `partner.provenance` is also preserved in the Partner DTO.
For `recommendation_origin=PARTNER_ANALYSIS`, `canonical_recommendation` records
the operational canonical action: `advance`, `pass`, `monitor`, or
`insufficient_evidence` (displayed as **More diligence** for this origin).
The legacy `partner.recommendation=MONITOR` compatibility value is unchanged;
new displays must not mistake that projection for a Partner decision to monitor.
Historical records lacking provenance retain their historical labels.
Lookup resolution can return `ambiguous` even with a supplied website when
retrieved evidence identifies competing domains and does not corroborate that
website. The existing candidate picker must obtain a deliberate identity choice;
canonical admission blocks disputed raw hints as `conflicting_domain_evidence`.
Supplying a domain is not proof that sources about similarly named firms belong
to that company.

Both `GET /api/opportunities/{opportunity_id}/evaluation` and
`GET /api/opportunities/{opportunity_id}/evidence` accept `view=analyst|full`.
The default remains `full` for existing API clients. The production app requests
`view=analyst`; development retains the full response for its provenance inspector.
The analyst evaluation view includes run ID/status/date, criterion scores,
reasoning, supporting/contradicting claim keys, limitations, validation/change
explanations, recommendation rationale and dependency status. It omits the raw
claim snapshot, model/prompt manifests, policy hashes and duplicated audit objects.
Only score/recommendation origins remain in its provenance object. Audit-only
evaluation fields are optional in the typed client. The analyst evidence view
retains source descriptions/URLs, excerpts, claim explanations and the identifiers
needed to join them; it omits execution plans, storage references, normalized raw
payloads and other unconsumed fields. Restricted-source URL redaction applies to
both views. Authentication and tenant scope are unchanged.

`POST /api/opportunities/manual-lookup` additionally returns `pipeline_run_id`
and an ordered `pipeline_trace` of the shared factual-evidence → Reviewer → validation → Partner path and compatibility projections.
No new debug endpoint or access policy is introduced. Existing authenticated,
tenant-scoped routes retain their guards. These fields are internal audit data;
the normal analyst UI does not render raw identifiers. In development, expand
**Development provenance** in a Flow memo to inspect them. See
[the provenance operating guide](docs/operations/pipeline-provenance.md).

## Monitoring and refresh budgets

| Method | Path | Notes |
|---|---|---|
| `POST` | `/api/opportunities/{opportunity_id}/refresh` | Reserve a resource/cost envelope, accept a durable refresh job |
| `PATCH` | `/api/opportunities/{opportunity_id}/service-level` | Set service level 0–5 with a lifecycle reason |
| `GET` | `/api/opportunities/{opportunity_id}/monitoring` | Lifecycle, reservations, material-change checks |

## Imports, outcomes, confidential artifacts

| Method | Path | Notes |
|---|---|---|
| `POST` | `/api/imports/csv` | Bounded CSV / CRM CSV / event / referral intake through canonical identity |
| `GET` | `/api/imports/{import_batch_id}` | Row status (resolved / review-required / error) without raw CSV data |
| `POST` | `/api/imports/companies` | Direct company import |
| `POST` | `/api/opportunities/{opportunity_id}/confidential-artifacts` | Pitch-deck / email metadata with access + retention policy |
| `GET`/`POST` | `/api/companies/{company_id}/outcomes` | Immutable, evidence-backed later observations |
| `GET` | `/api/outcomes/coverage` | Coverage/valence disclosure; causal inference explicitly unsupported |

## Fund thesis

| Method | Path | Notes |
|---|---|---|
| `GET` | `/api/fund-thesis` | Active thesis, version list, embedding status, recent pipeline links |
| `GET` | `/api/fund-thesis/runtime` | Lightweight runtime shape for the system panel |
| `POST` | `/api/fund-thesis/versions` | Body includes `raw_text`; optional `parsed_json`, `skip_embedding`, `pipeline_run_id` |
| `PATCH` | `/api/fund-thesis/active` | Body `{version_id, pipeline_run_id?}` |
| `POST` | `/api/fund-thesis/reprocess-missing?dry_run=` | Re-run reviewer/partner where thesis linkage is missing |
| `POST` | `/api/fund-thesis/backfill-embeddings` | Backfill embeddings for existing versions |

All fund-thesis routes require Supabase and return `503` when it is unavailable.

## Settings and policy

| Method | Path | Notes |
|---|---|---|
| `GET` | `/api/settings` | User settings, meta-agent config view, inline system-health snapshot |
| `PATCH` | `/api/settings` | Partial update of `fund_identity`, `cost_budget`, `agent_config`, `portfolio`. `422` on validation failure |
| `POST` | `/api/settings/policy/preview` | Compile and preview a policy from the fund configuration |
| `POST` | `/api/settings/policy/publish` | Publish the compiled policy version |
| `GET` | `/api/policy/active` | Active policy pointer |
| `POST` | `/api/policy/reload` | Reload the policy cache without a restart |

## Fund intelligence (governed policy proposals)

| Method | Path | Notes |
|---|---|---|
| `POST` | `/api/fund-intelligence/derive-overrides` | Derive attributed observations and proposals |
| `GET` | `/api/fund-intelligence/observations` | Deterministic descriptive observations over historical Decision Cases; supports sector, stage, geography, thesis version, ISO date, and observation-type filters |
| `GET` | `/api/fund-intelligence/hypotheses` | Conservative descriptive hypotheses grounded only in sufficiently supported Fund Intelligence observations; supports the same context filters and hypothesis family |
| `GET` | `/api/fund-intelligence/hypotheses/{id}/replay` | Counterfactual replayability preview; fails closed when a hypothesis lacks a deterministic policy delta |
| `GET` | `/api/fund-intelligence/counterfactual-proposals` | Draft machine-readable adaptation proposals grounded in hypotheses; returns `insufficient_basis` when existing policy semantics cannot represent the change |
| `GET` | `/api/fund-intelligence/proposals` | Proposal inbox |
| `GET` | `/api/fund-intelligence/proposals/{id}` | Proposal detail |
| `POST` | `/api/fund-intelligence/proposals/{id}/preview` | Bounded preview; binds both policy and canonical-config hashes |
| `POST` | `/api/fund-intelligence/proposals/{id}/review` | Accept / edit / reject / defer. An edited acceptance receives a **restricted patch**, never a client-supplied full fund configuration, and creates a draft only |
| `POST` | `/api/fund-intelligence/policy-versions/{id}/publish` | Atomically publish the governed version; legacy settings project idempotently through the outbox |

## Authority rollout

| Method | Path | Notes |
|---|---|---|
| `GET` | `/api/authority/status` | Current rollout mode and reconciliation state |
| `POST` | `/api/authority/transition` | Optimistic-locked mode transition |
| `POST` | `/api/authority/rollback` | Roll back to the previous mode |
| `POST` | `/api/authority/replay-projection` | Replay the compatibility projection |
| `POST` | `/api/authority/reconciliation` | Run reconciliation |
| `POST` | `/api/authority/backfill` | Run the canonical backfill |

## Escalations, signals, activity

| Method | Path | Notes |
|---|---|---|
| `GET` | `/api/escalations` | Pending human-review escalations |
| `POST` | `/api/escalations/{startup_id}/resolve` | Body `{decision: "YES"\|"NO"\|"MAYBE", notes}`; writes `human_resolution` |
| `GET` | `/api/signals` | Last 50 portfolio signals with company names |
| `GET` | `/api/activity/summary` | "While you were away" summary |
| `POST` | `/api/activity/seen` | Mark activity as seen |

## Portfolio and analytics

| Method | Path | Notes |
|---|---|---|
| `GET` | `/api/portfolio/positions` | Canonical portfolio positions |
| `GET` | `/api/analytics/rejections` | Rejection analysis |
| `GET` | `/api/analytics/watchlist` | Watchlist quality |
| `GET` | `/api/analytics/concentration` | Sector concentration clustering |
| `GET` | `/api/analytics/system-health` | Pipeline health snapshot |

## Meta-agent

| Method | Path | Notes |
|---|---|---|
| `POST` | `/api/meta/trigger` | Run one meta-agent cycle |
| `GET` | `/api/meta/reports` | Latest 10 reports |
| `GET` | `/api/meta/insights` | Latest what-changed / why summary |
| `GET` | `/api/meta/prompt-library` | Prompt library document |
| `GET` | `/api/meta/prompt-state` | Active vs candidate prompt state |
| `POST` | `/api/meta/prompts/promote` | Promote a candidate prompt (may require a fresh eval pass) |
| `POST` | `/api/meta/prompts/reset` | Reset to the baseline prompt |
| `GET`/`PUT` | `/api/meta/eval-set` | The startup set used for prompt evaluation |
| `POST` | `/api/meta/prompts/evaluate` | Run a prompt evaluation |
| `GET` | `/api/meta/weights` | Current scout weighting |
| `GET` | `/api/meta/calibration` | Reviewer calibration state |

## Admin

| Method | Path | Notes |
|---|---|---|
| `POST` | `/api/admin/login` | Secret-based admin login; issues a short-TTL admin token. Failure-count limited |
| `GET` | `/api/admin/overview` | Cross-tenant operational overview. Access is audit-logged |

Admin routes are inert unless `ADMIN_DASHBOARD_ENABLED` and the admin secrets are
configured.

### Investment-review dependency validity

`GET /api/opportunities/{opportunity_id}/evaluation` adds optional `dependencies`:
`{state: "current" | "stale" | "unknown", reasons: string[], message: string}`.
For new investment reviews, this read-only check compares material factual evidence,
current evidence eligibility, thesis, policy and prompt versions. Stored historical
scores and decisions are not rewritten. The memo displays the human-readable
refresh message; reason codes remain API/audit metadata. Historical evaluations
without the new contracts report unknown. Partner-only refresh rejects changed
Reviewer dependencies; a full refresh safely reuses available factual evidence.
