-- =============================================================================
-- Startups: list_location projection from scout_info.location
-- =============================================================================

alter table public.startups
  add column if not exists list_location text
    generated always as (nullif(trim(scout_info->>'location'), '')) stored;

create index if not exists startups_user_list_location_idx
  on public.startups (user_id, list_location)
  where list_location is not null;
