-- Step 10: provider-neutral interoperability metadata. These IDs never replace
-- canonical Aethria identity and no connector/sync worker is introduced here.

create table if not exists public.external_entity_mappings (
  mapping_id uuid primary key default gen_random_uuid(),
  user_id text not null,
  provider text not null check (length(btrim(provider)) > 0),
  entity_type text not null check (entity_type in ('company','person','opportunity')),
  aethria_entity_id text not null check (length(btrim(aethria_entity_id)) > 0),
  external_entity_id text not null check (length(btrim(external_entity_id)) > 0),
  workspace_id text not null default 'default',
  sync_status text not null default 'unmapped' check (sync_status in ('unmapped','pending','synced','stale','error','retired')),
  last_synced_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id, mapping_id),
  unique (user_id, provider, workspace_id, entity_type, aethria_entity_id),
  unique (user_id, provider, workspace_id, entity_type, external_entity_id)
);
create index if not exists external_entity_mappings_lookup_idx
  on public.external_entity_mappings (user_id, provider, workspace_id, entity_type);

alter table public.external_entity_mappings enable row level security;
drop policy if exists external_entity_mappings_service_role_all on public.external_entity_mappings;
create policy external_entity_mappings_service_role_all on public.external_entity_mappings
  for all to service_role using (true) with check (true);
revoke all on table public.external_entity_mappings from anon, authenticated;
grant select, insert, update, delete on table public.external_entity_mappings to service_role;
