# Aethria DB — Long-Run Target Schema (full audit + migration design)

Date: 2026-06-13. Current: **27 tables, 99 indexes** on Supabase free (egress-restricted).
Target: **~12 tables**, ~half the indexes, ~90% smaller hot row. Designed for the plain-Postgres
migration (Oracle/Coolify) — do this *instead of* a 1:1 copy.

Evidence basis: live `pg_class`/`pg_stat` sizing + per-table code-reference scan (see verdict notes).

---

## Per-table verdict (all 27)

| Table | Rows | Verdict | Why |
|---|---|---|---|
| **startups** | 166 / 4.7 MB | **REDESIGN** | 29 KB/row; `review_info` = 20 KB/row = 64% of table. Split (below). |
| startup_pipeline_state | 174 | KEEP | Clean typed state machine; different write cadence than startups. |
| portfolio_startups | 133 | HISTORICAL ONLY | Live rows are preserved for provenance and reconciliation. Runtime reads and writes use `startups`; the table is intentionally absent from the provider-neutral schema. Live deletion/archive is a separate operational decision. |
| fund_thesis | 7 | KEEP | Well-modeled, FK to active version. |
| fund_thesis_versions | 43 | KEEP | Versioned thesis; fine. |
| fund_thesis_embeddings | 43 / 592 KB | **REDESIGN** | Vectors stored as **jsonb arrays**. Move to `pgvector vector(1536)`: ~half the bytes + real ANN index. |
| fund_thesis_pipeline_link | 45 | KEEP | Link table; fine. |
| settings | 6 / 264 KB | **MERGE → kv_store** | KV shape via doc-store. 54 KB/row — trim dead keys. |
| memory | 7 | MERGE → kv_store | KV shape. |
| serp_usage | — | **DROPPED** (2026-06-17) | SerpAPI removed; platform uses Tavily only. See migration `20260617000001_drop_serp_usage_table.sql`. |
| analytics_sector_concentration | 4 / 496 KB | **MERGE → kv_store** | 248 KB for 2 rows — recompute-on-read instead of persisting a fat blob. |
| meta_prompt_library | 2 / 144 KB | MERGE → kv_store | KV shape; prompt history accreting in one cell. |
| meta_scout_weights | 0 | MERGE → kv_store | KV shape, written by meta agent. |
| meta_calibration_state | 0 | MERGE → kv_store | KV shape. |
| meta_cycle_counters | 4 | MERGE → kv_store | KV shape. |
| meta_churn_signals | 0 | MERGE → kv_store | KV shape (read by meta/analyser). |
| fund_policy_versions | 1 | MERGE → kv_store | KV shape via doc-store. |
| portfolio_positions | 7 | MERGE → kv_store | KV via doc-store. |
| portfolio_decisions | 14 | MERGE → kv_store | KV via doc-store. |
| portfolio_rejections | 3 | MERGE → kv_store | KV via doc-store. |
| portfolio_watchlist | 4 | MERGE → kv_store | KV via doc-store. |
| portfolio_signals | 0 | MERGE → kv_store | KV via doc-store. |
| portfolio_budgets | 4 | MERGE → kv_store | KV via doc-store (cost_control). |
| portfolio_rejection_patterns | 2 | MERGE → kv_store | KV shape. |
| **meta_reports** | 596 / 1.2 MB | **MERGE → event_log + RETENTION** | Append-only log, never pruned, read whole by meta endpoint. |
| **portfolio_agent_metrics** | 985 | **MERGE → event_log + RETENTION** | Append-only metrics stream, unbounded. |
| meta_mutation_log | 9 | MERGE → event_log + retention | Append-only log. |
| lookup_job_outcomes | 82 | MERGE → event_log + retention | Append-only job results; TTL 7–30 days. |
| pipeline_activity | 536 | KEEP + RETENTION | Typed, queried for stats. Add 90-day prune. |
| admin_audit_log | 399 | KEEP + RETENTION | Typed audit; add retention per policy. |
| scoring_trails | 2 | KEEP + RETENTION | Append-only, read by recalibration. |
| security_limits | 22 | KEEP | Rate limiter via RPCs; leave as-is. |
| user_state | 3 | KEEP | last_seen tracking; tiny. |
| system_metrics | 44 | **DROP** (verify) | No active writer in code. Legacy. Or repoint the RSS sampler at it. |
| pipeline_runs | 0 | **DROP** | Empty, superseded by `pipeline_activity`. |
| runtime_events | 0 | **DROP** | Empty, zero code refs. |
| deployment_events | 0 | **DROP** | Empty, zero code refs (deploy-webhook never built). |
| agent_activity | 0 | **DROP** | Empty, zero code refs. |

**Summary:** DROP 5 · MERGE 17→1 (`kv_store`) · MERGE 4→1 (`event_log`) · REDESIGN 2 (`startups`, embeddings) · KEEP 8.

---

## Target schema (the important DDL)

### 1. `startups` — slim hot row (29 KB → ~1–2 KB/row)
Promote the ~12 display/query fields to real typed columns (drop the 20 generated `list_*` —
the promoted columns *are* the list columns). Keep small jsonb only for genuinely structured
extras. Move the heavy reviewer payload out.

```sql
create table startups (
  id              uuid primary key default gen_random_uuid(),
  user_id         text not null,
  startup_id      text not null,
  -- canonical scalars (were scout_info->>... + list_*)
  name            text,
  one_line        text,
  sector          text,
  location        text,
  scout_type      text,
  origin_type     text,
  confidence      double precision,
  -- review rollup (were review_info->>... + list_*)
  score           double precision,
  verdict         text,
  consensus_verdict text,
  reviewer_disagreement boolean default false,
  reviewed_at     timestamptz,
  -- partner rollup
  partner_decision text,
  human_review_required boolean default false,
  partnered_at    timestamptz,
  -- lifecycle
  status          text,            -- fold startup_pipeline_state if cadence allows
  first_seen_at   timestamptz default now(),
  acknowledged_at timestamptz,
  last_seen_by_user_at timestamptz,
  unresolved_at   timestamptz,
  queue_reason    text,
  priority_reason text,
  conviction_state jsonb,          -- small
  human_resolution jsonb,          -- small, nullable
  version         int default 1,
  created_at      timestamptz default now(),
  updated_at      timestamptz default now(),
  unique (user_id, startup_id)
);
-- indexes ONLY for real query paths (drop speculative location/lookup_id):
create index startups_user_updated_idx on startups (user_id, updated_at desc);
create index startups_user_decision_idx on startups (user_id, partner_decision);
```

### 2. `startup_reviews` — heavy detail, read on-demand (kills the 20 KB egress drag)
```sql
create table startup_reviews (
  user_id     text not null,
  startup_id  text not null,
  scout_info  jsonb,      -- full scout payload
  review_info jsonb,      -- the 3-persona reviewer blob (20 KB)
  partner_info jsonb,     -- full partner payload
  agent_trace jsonb,
  financials  jsonb,
  investment_memo_markdown text,
  updated_at  timestamptz default now(),
  primary key (user_id, startup_id)
);
```
List/stats/grid reads never touch this table. Only the detail/memo endpoint joins it.

### 3. `kv_store` — replaces ~17 KV tables
```sql
create table kv_store (
  namespace  text not null,   -- 'settings','memory','portfolio_positions',...
  user_id    text not null,
  key        text not null default '',
  data       jsonb not null default '{}',
  updated_at timestamptz default now(),
  primary key (namespace, user_id, key)
);
```
Code change is small: the doc-store already maps logical name → table; change it to map
logical name → `namespace` and route all `doc_get/doc_set/list_get_all` through `kv_store`.

### 4. `event_log` — replaces the append-only jsonb logs + retention
```sql
create table event_log (
  id         bigserial primary key,
  user_id    text not null,
  kind       text not null,   -- 'meta_report','agent_metric','mutation','lookup_outcome'
  created_at timestamptz default now(),
  data       jsonb not null default '{}'
);
create index event_log_user_kind_created_idx on event_log (user_id, kind, created_at desc);
-- retention (cron / pg_cron):
-- delete from event_log where created_at < now() - interval '90 days';
```

### 5. `fund_thesis_embeddings` — pgvector
```sql
create extension if not exists vector;
alter table fund_thesis_embeddings
  add column embedding vector(1536);   -- backfill from jsonb, then drop the jsonb column
create index on fund_thesis_embeddings using ivfflat (embedding vector_cosine_ops);
```

---

## Migration order (safe, incremental)
1. **Quick win now (still on Supabase):** `DROP` the 5 dead tables + the zero-scan speculative
   indexes (`startups_user_list_location_idx`, `startups_user_list_lookup_id_idx`, redundant
   `*_user_id_idx` covered by composite PKs). Pure cleanup, no app change.
2. **`startups` split** — biggest egress win. New `startup_reviews`, backfill, repoint detail/memo
   reads, then slim `startups`. Do behind the storage layer (`legacy_supabase/storage.py`) so callers don't change.
3. **`kv_store` collapse** — route doc-store through it; migrate data namespace by namespace.
4. **`event_log` + retention** — move the 4 logs; add the prune job.
5. **pgvector** — last; needs the extension (trivial on self-hosted Postgres).

Steps 1–2 are the egress fixes. Steps 3–5 are long-run cleanliness best done during the move.

---

## Status / decisions (2026-06-13)
- **Step 1 — DONE, live on prod.** `20260613000001_drop_dead_tables_and_indexes.sql` applied. 27 → 22 tables.
- **Step 2 — migrations written, code NOT yet done.** `..._startups_split_expand.sql` (safe/additive)
  and `..._startups_split_contract.sql` (apply only after code deploy) on branch
  `refactor/startups-split-review-detail`. Reframed: the read layer is **already egress-optimized**
  (prior ~10x work: `_LIST_SELECT` thin projection, `count="exact"`, `_DECISION_SCAN_SELECT`,
  `_MEMO_PARTIAL_SELECT`). So the split's payoff is schema cleanliness + lower storage/list-egress,
  not an emergency fix. **Best landed WITH the Postgres migration**, where it can be tested. Do not
  apply contract to Supabase prod untested.
- **Steps 3–5 — do during the Postgres migration**, not on Supabase (avoids double work).

### Code changes the contract depends on (`backend/legacy_supabase/storage.py`)
The expand/contract DDL is inert until these land. Scope = move `review_info`/`agent_trace`/
`financials`/`investment_memo_markdown` to `startup_reviews`; keep `scout_info`/`partner_info` on the row.
1. **`_dict_to_row`** — stop writing `review_info`/`agent_trace`/`financials`/`investment_memo_markdown`
   into the startups row; also set the new plain `review_*` scalars (extract from review payload).
2. **New `_reviews_row(d, user_id)`** — build the `startup_reviews` row; upsert it alongside the
   startups upsert in `upsert_startup_dict` / `replace_all` (write both tables per startup).
3. **`_row_to_dict`** — `review_info`/`agent_trace`/`financials`/memo no longer on the row; for full
   reads, fetch the matching `startup_reviews` row and merge.
4. **`get_startup` (full)** — after fetching the startups row, fetch `startup_reviews` by
   `(user_id, startup_id)` and merge before `Startup.from_dict`.
5. **`get_startup_for_memo` / `_MEMO_PARTIAL_SELECT`** — read `review_info`/`agent_trace`/memo from
   `startup_reviews` instead of startups.
6. **`get_undecided`, `get_startups_with_review`, `get_startups_with_decision`, `get_startups_missing_thesis`** —
   these need `review_info`; switch from `select("*")` on startups to a join/secondary fetch of
   `startup_reviews` (or keep returning lean models + lazy-load reviews where the consumer allows).
7. Keep the existing missing-column fallback pattern (`_is_missing_*_error`) for a smooth rollout.
**Verify** against `backend/tests/` (esp. `test_egress_optimizations.py`, `test_memory_safety.py`)
before applying contract.
