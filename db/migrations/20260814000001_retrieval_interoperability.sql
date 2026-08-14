-- Provider-neutral retrieval cache, judgment audit, and interoperability tables.
-- Supabase-specific RLS and grants remain in the matching compatibility overlays.

alter table public.evaluation_runs
  add column if not exists judgment_audit jsonb not null default '{}'::jsonb;

create table if not exists public.retrieval_cache_entries (
  retrieval_cache_entry_id uuid primary key default gen_random_uuid(),
  user_id text not null,
  query_identity text not null,
  normalized_query text not null,
  category text not null check (category in ('general','news','company','people')),
  target_company_id text,
  target_person_id text,
  provider text not null,
  status text not null check (status in ('success','failure')),
  sources jsonb not null default '[]'::jsonb,
  diagnostics jsonb not null default '[]'::jsonb,
  fetched_at timestamptz not null default now(),
  last_success_at timestamptz,
  updated_at timestamptz not null default now(),
  unique (user_id, query_identity)
);
create index if not exists retrieval_cache_entries_fresh_idx
  on public.retrieval_cache_entries (user_id, query_identity, fetched_at desc)
  where status = 'success';

create table if not exists public.retrieval_cache_content_versions (
  retrieval_cache_content_version_id uuid primary key default gen_random_uuid(),
  user_id text not null,
  source_url text not null,
  canonical_url text not null,
  title text,
  content text,
  content_reference text,
  content_hash text not null check (length(content_hash) >= 8),
  published_at timestamptz,
  access_class text not null check (access_class in ('public','tenant_private','restricted')),
  provider_metadata jsonb not null default '{}'::jsonb,
  retrieved_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  unique (user_id, retrieval_cache_content_version_id),
  unique (user_id, content_hash, access_class)
);
create index if not exists retrieval_cache_content_url_idx
  on public.retrieval_cache_content_versions (user_id, canonical_url, retrieved_at desc);

create table if not exists public.retrieval_cache_observations (
  retrieval_cache_observation_id uuid primary key default gen_random_uuid(),
  user_id text not null,
  query_identity text not null,
  content_version_id uuid,
  provider text not null,
  observed_at timestamptz not null default now(),
  metadata jsonb not null default '{}'::jsonb,
  foreign key (user_id, content_version_id)
    references public.retrieval_cache_content_versions
      (user_id, retrieval_cache_content_version_id)
);
create index if not exists retrieval_cache_observations_query_idx
  on public.retrieval_cache_observations (user_id, query_identity, observed_at desc);

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

create table if not exists public.company_competitors (
  relationship_id uuid primary key default gen_random_uuid(),
  user_id text not null,
  target_company_id uuid not null,
  competitor_company_id uuid not null,
  relationship_type text not null check (relationship_type in ('product_overlap','segment_overlap','geography_overlap','competitor')),
  confidence double precision not null default 0 check (confidence between 0 and 1),
  status text not null default 'probable' check (status in ('verified','probable','conflicting','unknown','stale')),
  source_claim_id uuid,
  valid_from timestamptz,
  valid_to timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id, relationship_id),
  unique (user_id, target_company_id, competitor_company_id, relationship_type),
  check (target_company_id <> competitor_company_id),
  foreign key (user_id, target_company_id)
    references public.companies (user_id, company_id),
  foreign key (user_id, competitor_company_id)
    references public.companies (user_id, company_id),
  foreign key (user_id, source_claim_id)
    references public.claims (user_id, claim_id)
);
create index if not exists company_competitors_target_idx
  on public.company_competitors (user_id, target_company_id);
create index if not exists company_competitors_competitor_idx
  on public.company_competitors (user_id, competitor_company_id);
