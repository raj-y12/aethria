# API Reference

Base URL (local): `http://localhost:8000`

## Authentication

- Private routes require `Authorization: Bearer <clerk_jwt>`.
- Public routes: `GET /health` (and OpenAPI/doc routes).
- Auth failures return `401` with `{"detail":"Missing or invalid authorization token"}`.

## Health and Identity

- `GET /health` -> service heartbeat.
- `GET /api/me` -> current authenticated `user_id`.

## Startups and Memo

- `GET /api/startups`
  - Returns list-friendly startup projection for the work grid.
- `GET /api/startups/{startup_id}`
  - Returns full startup scout/review/partner payload.
- `GET /api/startups/{startup_id}/memo`
  - Returns memo state object:
  - `status: "ready" | "generating" | "failed"`
  - `memo: string | null`
  - `partial: {scout,review,partner} | null`
  - `pipeline_run_id: string | null`
  - `error: string | null`

## On-Demand Lookup

- `POST /api/startups/lookup`
  - Body: `{ "lookup_input": string, "lookup_id"?: string }`
  - Queues lookup job for the current user.
  - Returns `202` with queued metadata and resolved `lookup_id`.
- `GET /api/startups/lookup-status?lookup_id=<id>`
  - Reports failed lookup jobs when worker records outcome.

## Durable Jobs and Canonical Identity

- `GET /api/jobs`, `GET /api/jobs/{job_id}` -> tenant-scoped accepted/running/retry/blocked/final state.
- `POST /api/jobs/{job_id}/retry`, `POST /api/jobs/{job_id}/cancel` -> explicit recovery controls.
- `GET /api/companies/{company_id}`, `GET /api/opportunities/{opportunity_id}` -> canonical records.
- `GET /api/observations`, `GET /api/identity-cases` -> bounded source and ambiguity queues.
- `POST /api/identity-cases/{identity_case_id}/resolve` -> explicit match/create/defer/reject ruling.

## Evidence, Evaluation, and Human Decisions

- `GET /api/opportunities/{opportunity_id}/evidence` -> redacted artifact/claim/evidence ledger.
- `POST /api/opportunities/{opportunity_id}/evidence-plans` -> bounded diligence plan.
- `POST /api/claims/{claim_id}/correct` -> append an operator correction.
- `GET /api/opportunities/{opportunity_id}/evaluation` -> current immutable evaluation and recommendation.
- `POST /api/opportunities/{opportunity_id}/evaluate` -> explicit operator refresh.
- `POST /api/opportunities/{opportunity_id}/rulings` -> authoritative human ruling.
- `GET/POST /api/opportunities/{opportunity_id}/actions` -> workflow actions and drafts.
- `POST /api/actions/{workflow_action_id}/approve` -> approval record; does not itself claim an external write.

## Monitoring and Refresh Budgets

- `POST /api/opportunities/{opportunity_id}/refresh` -> reserve a resource/cost envelope and accept a durable refresh job.
- `PATCH /api/opportunities/{opportunity_id}/service-level` -> set service level 0–5 with lifecycle reason.
- `GET /api/opportunities/{opportunity_id}/monitoring` -> lifecycle, reservations, and material-change checks.

## Fund Intelligence

- `POST /api/fund-intelligence/derive-overrides` -> derive attributed observations/proposals.
- `GET /api/fund-intelligence/proposals` and `GET /api/fund-intelligence/proposals/{id}` -> proposal inbox/detail.
- `POST /api/fund-intelligence/proposals/{id}/preview` -> bounded preview for a server-applied stored patch or a restricted `rubric`/`scoringWeights` edit; binds both policy and canonical-config hashes.
- `POST /api/fund-intelligence/proposals/{id}/review` -> accept/edit/reject/defer; edited acceptance receives a restricted patch, never a client-supplied full fund configuration, and creates a draft only.
- `POST /api/fund-intelligence/policy-versions/{id}/publish` -> atomically publishes the governed PostgreSQL version; legacy settings are projected idempotently through the outbox.

## Imports, Confidential Artifacts, and Outcomes

- `POST /api/imports/csv` -> bounded CSV/CRM CSV/event/referral intake through canonical identity.
- `GET /api/imports/{import_batch_id}` -> resolved/review-required/error row status without raw CSV data.
- `POST /api/opportunities/{opportunity_id}/confidential-artifacts` -> pitch-deck/email metadata registration with confidential access and retention policy.
- `GET/POST /api/companies/{company_id}/outcomes` -> immutable, evidence-backed later observations.
- `GET /api/outcomes/coverage` -> coverage/valence disclosure with causal inference explicitly unsupported.

## Settings and Policy

- `GET /api/settings`
  - Returns user settings, meta-agent config view, and inline system-health snapshot.
- `PATCH /api/settings`
  - Partially updates settings sections (`fund_identity`, `cost_budget`, `agent_config`, `portfolio`).
  - Returns `422` on validation failures.
- `GET /api/policy/active`
  - Returns active policy pointer JSON.
- `POST /api/policy/reload`
  - Reloads policy cache without restart.

## Agents

- `POST /api/agents/trigger`
  - Enqueues one pipeline cycle for current user.
  - Common responses:
  - `202`: `{"status":"queued"}`
  - `200`: skipped due to disabled agents/supabase/thesis requirements
  - `503`: worker unavailable
- `GET /api/agents/status`
  - Returns readiness diagnostics:
  - worker state, Supabase/OpenAI configuration, thesis readiness.

## Meta-Agent

- `POST /api/meta/trigger` -> run one meta-agent cycle.
- `GET /api/meta/reports` -> latest 10 reports.
- `GET /api/meta/insights` -> latest what-changed/why summary.
- `GET /api/meta/prompt-library` -> prompt library document.
- `GET /api/meta/weights` -> current scout weighting state.
- `GET /api/meta/calibration` -> reviewer calibration state.

## Escalations and Signals

- `GET /api/escalations`
  - Pending human-review escalations.
- `POST /api/escalations/{startup_id}/resolve`
  - Body: `{ "decision":"YES|NO|MAYBE", "notes": string }`
  - Writes `human_resolution` for the startup.
- `GET /api/signals`
  - Returns last 50 portfolio signals with startup names.

## Analytics

- `GET /api/analytics/rejections`
- `GET /api/analytics/watchlist`
- `GET /api/analytics/concentration`
- `GET /api/analytics/system-health`

All analytics are user-scoped when running in authenticated/supabase mode.

## Fund Thesis

- `GET /api/fund-thesis`
  - Active thesis, version list, embedding status, recent pipeline links.
- `GET /api/fund-thesis/runtime`
  - Lightweight runtime shape for UI system panel.
- `POST /api/fund-thesis/versions`
  - Body includes `raw_text`; optional `parsed_json`, `skip_embedding`, `pipeline_run_id`.
- `PATCH /api/fund-thesis/active`
  - Body: `{ "version_id": string, "pipeline_run_id"?: string }`
- `POST /api/fund-thesis/reprocess-missing?dry_run=<bool>`
  - Re-runs reviewer/partner where thesis linkage is missing.

Fund-thesis endpoints require Supabase configuration and return `503` when unavailable.
