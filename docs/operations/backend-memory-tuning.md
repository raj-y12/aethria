# Backend Memory Audit

Date: 2026-05-29

Scope: `backend/` memory pressure, full-table reads, background processing, Supabase access patterns, API endpoints, analytics, and safe low-risk fixes.

## Executive Summary

The most likely Render memory pressure is cumulative rather than a single leak:

- persistent per-user agent loops can run in addition to queued trigger jobs;
- startup resume reads every settings row and can start many loops by default;
- several admin/meta/analytics paths still read all rows or all JSON-list documents synchronously;
- some fallback paths still materialize all startup rows;
- reviewer cycles intentionally run three reviewer LLM calls per startup and can hold multiple large reviewer responses before persisting.

The current code already contains several memory-safety improvements: `/api/startups` uses a bounded list projection in Supabase mode, reviewer and partner cycles have batch limits, and portfolio execution/cluster analysis use bounded scans when Supabase helpers are available.

## Critical

### 1. Persistent loops plus queued jobs can duplicate pipeline work

Affected files/functions:

- `backend/api.py::_agent_worker`
- `backend/api.py::_user_agent_loop`
- `backend/api.py::_ensure_user_loop`
- `backend/api.py::trigger_agents`
- `backend/pipeline_concurrency.py::pipeline_execution_slot`

Why it matters:

`POST /api/agents/trigger` enqueues one cycle and then also calls `_ensure_user_loop()`. The queue worker and persistent loop both call `run_one_pipeline_cycle(user_id)`. Per-user locking prevents same-user overlap, but the persistent loop can continue indefinitely after login, and multiple users can each hold a long-running loop task. On small Render instances this creates repeated memory spikes from scout/reviewer/partner/meta objects and LLM responses.

Estimated memory impact:

High. A single active cycle can instantiate 4 scouts, 3 reviewers, partner, portfolio, meta analysis, OpenAI clients, and transient LLM payloads. Multiple active users can push memory above a 512 MB instance even without a classic leak.

Recommended fix:

Production should set `RESUME_AGENT_LOOPS_ON_STARTUP=false`, `MAX_RESUMED_AGENT_LOOPS=3` or lower, and `MAX_CONCURRENT_PIPELINE_CYCLES=1`. Later, choose one execution model: queued one-shot cycles or persistent loops, not both by default.

Implementation difficulty:

Medium if changing behavior; low for production env changes.

Estimated memory reduction:

High under multi-user load.

### 2. Startup resume reads all settings and can restart all loops

Affected files/functions:

- `backend/api.py::_resume_all_user_loops`

Why it matters:

At startup the function runs `settings.select("user_id,data").execute()` without pagination or a database-side filter, then scans every settings JSON blob in memory. Default `RESUME_AGENT_LOOPS_ON_STARTUP` is `true` and `MAX_RESUMED_AGENT_LOOPS=0` means no cap.

Estimated memory impact:

Medium to high depending on user count and settings JSON size. The larger risk is not the settings rows themselves, but the loops started from them.

Recommended fix:

Make production defaults conservative or filter/cap at the query level. Keep current behavior documented until deploy settings are changed.

Implementation difficulty:

Low for env defaults, medium for schema/query improvements.

Estimated memory reduction:

Medium at boot; high if it prevents loop storms.

## High Impact

### 3. Admin overview performs cross-tenant full-table reads

Affected files/functions:

- `backend/api.py::admin_overview`
- `backend/admin/service.py::build_admin_overview`
- `backend/admin/service.py::_fetch_rows`

Why it matters:

The admin overview reads all settings, all startup `user_id,partner_decision` rows, and all pipeline activity rows for every tenant, then aggregates in Python. This is synchronous on request.

Estimated memory impact:

Medium to high if startup/pipeline_activity grows. It is cross-tenant, so growth is global rather than per user.

Recommended fix:

Replace with database-side counts/grouping or bounded recent windows. Keep the endpoint shape but compute totals with SQL/RPC or paginated aggregation.

Implementation difficulty:

Medium.

Estimated memory reduction:

High on admin requests.

### 4. Meta reports and mutation logs are read in full

Affected files/functions:

- `backend/api.py::get_meta_reports`
- `backend/api.py::get_meta_insights`
- `backend/meta/analyser.py::_read_agent_metrics`
- `backend/meta/analyser.py::_read_mutation_log`
- `backend/meta/mutator.py::_read_json_list`
- `backend/legacy_supabase/doc_store.py::list_get_all`

Why it matters:

Meta endpoints return only the latest/summarized data, but first load all rows from `meta_reports` or `meta_mutation_log`. The MetaAgent also reads full metrics/log lists during each pipeline cycle.

Estimated memory impact:

Medium now, high as meta history grows. Reports can embed `signal_summary` and prompt proposals.

Recommended fix:

Add bounded list reads for “latest N” endpoints and prune or archive old meta history. Use targeted reads for active records where possible.

Implementation difficulty:

Low to medium.

Estimated memory reduction:

Medium.

### 5. Startup storage has full-row/full-table fallback paths

Affected files/functions:

- `backend/legacy_supabase/storage.py::_fetch_all_raw`
- `backend/legacy_supabase/storage.py::get_all_startups`
- `backend/legacy_supabase/storage.py::get_all`
- `backend/legacy_supabase/storage.py::_atomic_update`
- `backend/legacy_supabase/storage.py::replace_all`
- `backend/legacy_supabase/storage.py::_legacy_get_startups_with_decision`
- `backend/legacy_supabase/storage.py::get_startups_requiring_human_review` fallback
- `backend/legacy_supabase/storage.py::count_unreviewed` fallback
- `backend/legacy_supabase/storage.py::count_undecided` fallback

Why it matters:

Normal Supabase pipeline paths mostly use targeted queries, but fallback paths still materialize every startup and sometimes delete/rewrite all user rows. If a column/index/migration is missing or a query fails, fallback can become the memory-heavy path.

Estimated memory impact:

High for tenants with many rich startup JSON rows, especially rows containing `agent_trace`, `review_info.reviews`, structured scoring, and memo markdown.

Recommended fix:

Keep `replace_all` restricted to migration/dev tooling. Remove read-all fallbacks from request/runtime paths once migrations are guaranteed. Add tests that production endpoints never call `get_all()` in Supabase mode.

Implementation difficulty:

Medium.

Estimated memory reduction:

High during failure/fallback scenarios.

## Medium Impact

### 6. Analytics reads and recomputes full report inputs synchronously

Affected files/functions:

- `backend/api.py::get_signals`
- `backend/api.py::get_watchlist_analytics`
- `backend/api.py::get_rejection_analytics`
- `backend/api.py::get_system_health`
- `backend/portfolio/health.py::_run_cluster_analysis`
- `backend/analytics/clustering.py::SectorClusterAnalyzer.analyze`

Why it matters:

Signals/watchlist analytics load full list-document tables, attach startup names via a full startup-id/name map, and sort/aggregate in process. Cluster analysis is O(n²) over the bounded startup slice.

Estimated memory impact:

Medium. The current limits reduce risk, but list-doc tables can still grow.

Recommended fix:

Add bounded list reads for signals/watchlist, database-side counts for system health, and cap name-map reads where feasible.

Implementation difficulty:

Medium.

Estimated memory reduction:

Medium.

### 7. Activity summary can read all historical activity on first visit

Affected files/functions:

- `backend/api.py::get_activity_summary`

Why it matters:

If `last_seen_at` is missing, the endpoint uses `1970-01-01T00:00:00Z` and reads all `pipeline_activity` rows for the user, then aggregates in Python.

Estimated memory impact:

Low to medium per user; grows with pipeline cycle history.

Recommended fix:

Aggregate in SQL or cap the historical window while preserving response semantics with precomputed totals.

Implementation difficulty:

Medium.

Estimated memory reduction:

Low to medium.

## Low Impact

### 8. DealMemory repeatedly reads/writes the full memory document

Affected files/functions:

- `backend/memory.py::DealMemory._read`
- `backend/memory.py::DealMemory.record_scout_discovery`
- `backend/memory.py::DealMemory.record_failed_assumptions`
- `backend/memory.py::DealMemory.record_successful_thesis`

Why it matters:

The lists are capped, so this is not a major memory leak. It does cause repeated JSON serialization/deserialization within a pipeline cycle.

Estimated memory impact:

Low.

Recommended fix:

Leave as-is unless memory documents become large. The current caps are useful.

Implementation difficulty:

Low.

Estimated memory reduction:

Low.

### 9. Local JSON fallback storage is intentionally read-all/write-all

Affected files/functions:

- `backend/utils/storage.py`
- `backend/portfolio/store.py` local fallback methods

Why it matters:

This is acceptable for dev fallback but not production-scale. Production should use Supabase and avoid local fallback for pipeline execution.

Estimated memory impact:

Low in production if `USE_SUPABASE_STORAGE=1`; high if accidentally deployed with file fallback.

Recommended fix:

Keep production gate requiring Supabase for pipeline execution.

Implementation difficulty:

Low.

Estimated memory reduction:

N/A if production is already Supabase-only.

## Diagnostics Added

- `backend/pipeline_runner.py`
  - current RSS before pipeline cycle;
  - current RSS after pipeline cycle;
  - processing duration;
  - startup count before/after;
  - startups found/reviewed/decided/escalated;
  - approximate agent count executed.

- `backend/memo_generator.py`
  - current RSS before memo generation;
  - current RSS after memo generation;
  - memo generation duration;
  - generated memo character count.

No external monitoring service was added.

## Safe Fix Implemented

### Targeted portfolio list upsert version lookup

Affected file/function:

- `backend/portfolio/store.py::_append_record`

Change:

For Supabase-backed non-startup portfolio list tables, `_append_record` previously loaded all rows via `list_get_all(table)` only to find one existing record and increment its version. It now uses `list_get_by_id(table, record_id)` and then `list_upsert`.

Why it is safe:

The record id, version increment behavior, and upsert behavior are preserved. The change only avoids loading unrelated rows.

Estimated memory reduction:

Low to medium per portfolio append/update, depending on table size.

## Deferred Fixes

These are likely useful but intentionally not implemented in this pass:

- Choose one production agent execution model: queued trigger or persistent loop.
- Query/filter `_resume_all_user_loops` at the database level and use conservative production defaults.
- Replace admin overview full-table reads with database-side aggregation.
- Add bounded/recent list read helpers for meta reports, mutation logs, signals, and watchlist analytics.
- Remove Supabase runtime fallback paths that call `get_all_startups()` after migrations are guaranteed.
- Add database-side aggregation for activity summary.
- Add retention policies for append-only meta and pipeline activity tables.
