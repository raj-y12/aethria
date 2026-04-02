-- =============================================================================
-- On-demand lookup: stable correlation id (scout_info.lookup_id) for list API
-- =============================================================================
-- Matches backend scout payload set by ScoutEngine.run_named_lookup.
-- Idempotent: safe to re-run if column already exists.
-- =============================================================================

alter table public.startups
  add column if not exists list_lookup_id text
    generated always as (nullif(trim(scout_info->>'lookup_id'), '')) stored;

create index if not exists startups_user_list_lookup_id_idx
  on public.startups (user_id, list_lookup_id)
  where list_lookup_id is not null;
