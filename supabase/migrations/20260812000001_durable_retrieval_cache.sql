-- Durable provider-neutral retrieval observations. These tables are deliberately
-- separate from the canonical evidence/claim ledger.
create extension if not exists pgcrypto;

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

create table if not exists public.retrieval_cache_observations (
  retrieval_cache_observation_id uuid primary key default gen_random_uuid(),
  user_id text not null,
  query_identity text not null,
  content_version_id uuid,
  provider text not null,
  observed_at timestamptz not null default now(),
  metadata jsonb not null default '{}'::jsonb,
  foreign key (user_id, content_version_id)
    references public.retrieval_cache_content_versions (user_id, retrieval_cache_content_version_id)
);

create index if not exists retrieval_cache_entries_fresh_idx
  on public.retrieval_cache_entries (user_id, query_identity, fetched_at desc)
  where status = 'success';
create index if not exists retrieval_cache_content_url_idx
  on public.retrieval_cache_content_versions (user_id, canonical_url, retrieved_at desc);
create index if not exists retrieval_cache_observations_query_idx
  on public.retrieval_cache_observations (user_id, query_identity, observed_at desc);

alter table public.retrieval_cache_entries enable row level security;
alter table public.retrieval_cache_content_versions enable row level security;
alter table public.retrieval_cache_observations enable row level security;

drop policy if exists retrieval_cache_entries_tenant on public.retrieval_cache_entries;
drop policy if exists retrieval_cache_content_versions_tenant on public.retrieval_cache_content_versions;
drop policy if exists retrieval_cache_observations_tenant on public.retrieval_cache_observations;

-- Direct PostgreSQL workers use an explicitly tenant-scoped repository. The
-- policy also protects sessions that set app.user_id, without depending on a
-- Supabase auth function.
create policy retrieval_cache_entries_tenant on public.retrieval_cache_entries
  using (user_id = current_setting('app.user_id', true));
create policy retrieval_cache_content_versions_tenant on public.retrieval_cache_content_versions
  using (user_id = current_setting('app.user_id', true));
create policy retrieval_cache_observations_tenant on public.retrieval_cache_observations
  using (user_id = current_setting('app.user_id', true));
