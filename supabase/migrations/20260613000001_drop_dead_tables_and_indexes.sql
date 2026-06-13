-- Schema cleanup (audit 2026-06-13): drop tables with zero code references
-- (no readers, no writers) and zero-scan speculative indexes on startups.
-- See SUPABASE_SCHEMA_AUDIT.md. Reversible (recreate from history); dropped
-- data is orphaned metrics/empty event tables with no consumer.

-- Dead tables: empty + no .table() reference anywhere in backend/ (excl tests).
--   runtime_events, deployment_events, agent_activity : empty, never wired up.
--   pipeline_runs   : empty, superseded by pipeline_activity.
--   system_metrics  : 44 legacy rows, no reader and no writer in code.
drop table if exists public.runtime_events;
drop table if exists public.deployment_events;
drop table if exists public.agent_activity;
drop table if exists public.pipeline_runs;
drop table if exists public.system_metrics;

-- Speculative indexes on columns never used in a WHERE/ORDER (no code filters
-- by location or lookup_id). Zero scans since the Jun-10 index rebuild.
drop index if exists public.startups_user_list_location_idx;
drop index if exists public.startups_user_list_lookup_id_idx;
