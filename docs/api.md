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
