-- Fund thesis: versioned, tenant-isolated; embeddings as JSON array (no pgvector required).
-- Service role writes from backend; JWT users read own rows.

create table if not exists public.fund_thesis (
  id uuid primary key default gen_random_uuid(),
  user_id text not null unique,
  active_version_id uuid,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

create table if not exists public.fund_thesis_versions (
  id uuid primary key default gen_random_uuid(),
  user_id text not null,
  thesis_id uuid not null references public.fund_thesis (id) on delete cascade,
  version_number int not null,
  raw_text text not null default '',
  parsed_json jsonb not null default '{}'::jsonb,
  is_active boolean not null default false,
  created_at timestamptz not null default timezone('utc', now()),
  constraint fund_thesis_versions_thesis_version_unique unique (thesis_id, version_number)
);

create index if not exists fund_thesis_versions_user_id_idx on public.fund_thesis_versions (user_id);
create index if not exists fund_thesis_versions_thesis_id_idx on public.fund_thesis_versions (thesis_id);

create table if not exists public.fund_thesis_embeddings (
  id uuid primary key default gen_random_uuid(),
  user_id text not null,
  version_id uuid not null references public.fund_thesis_versions (id) on delete cascade,
  embedding_vector jsonb not null default '[]'::jsonb,
  model text not null default 'text-embedding-3-small',
  created_at timestamptz not null default timezone('utc', now()),
  constraint fund_thesis_embeddings_version_unique unique (version_id)
);

create index if not exists fund_thesis_embeddings_user_id_idx on public.fund_thesis_embeddings (user_id);

-- Links thesis activation to pipeline context (pipeline_run_id nullable for thesis-only events).
create table if not exists public.fund_thesis_pipeline_link (
  id uuid primary key default gen_random_uuid(),
  user_id text not null,
  thesis_version_id uuid not null references public.fund_thesis_versions (id) on delete cascade,
  pipeline_run_id uuid,
  affected_startups_count int not null default 0,
  created_at timestamptz not null default timezone('utc', now())
);

create index if not exists fund_thesis_pipeline_link_user_idx on public.fund_thesis_pipeline_link (user_id);
create index if not exists fund_thesis_pipeline_link_version_idx on public.fund_thesis_pipeline_link (thesis_version_id);

alter table public.fund_thesis enable row level security;
alter table public.fund_thesis_versions enable row level security;
alter table public.fund_thesis_embeddings enable row level security;
alter table public.fund_thesis_pipeline_link enable row level security;

drop policy if exists "Users read own fund_thesis" on public.fund_thesis;
create policy "Users read own fund_thesis"
  on public.fund_thesis for select
  using (auth.jwt() ->> 'sub' = user_id);

drop policy if exists "Service role full access fund_thesis" on public.fund_thesis;
create policy "Service role full access fund_thesis"
  on public.fund_thesis for all
  using (auth.role() = 'service_role')
  with check (auth.role() = 'service_role');

drop policy if exists "Users read own fund_thesis_versions" on public.fund_thesis_versions;
create policy "Users read own fund_thesis_versions"
  on public.fund_thesis_versions for select
  using (auth.jwt() ->> 'sub' = user_id);

drop policy if exists "Service role full access fund_thesis_versions" on public.fund_thesis_versions;
create policy "Service role full access fund_thesis_versions"
  on public.fund_thesis_versions for all
  using (auth.role() = 'service_role')
  with check (auth.role() = 'service_role');

drop policy if exists "Users read own fund_thesis_embeddings" on public.fund_thesis_embeddings;
create policy "Users read own fund_thesis_embeddings"
  on public.fund_thesis_embeddings for select
  using (auth.jwt() ->> 'sub' = user_id);

drop policy if exists "Service role full access fund_thesis_embeddings" on public.fund_thesis_embeddings;
create policy "Service role full access fund_thesis_embeddings"
  on public.fund_thesis_embeddings for all
  using (auth.role() = 'service_role')
  with check (auth.role() = 'service_role');

drop policy if exists "Users read own fund_thesis_pipeline_link" on public.fund_thesis_pipeline_link;
create policy "Users read own fund_thesis_pipeline_link"
  on public.fund_thesis_pipeline_link for select
  using (auth.jwt() ->> 'sub' = user_id);

drop policy if exists "Service role full access fund_thesis_pipeline_link" on public.fund_thesis_pipeline_link;
create policy "Service role full access fund_thesis_pipeline_link"
  on public.fund_thesis_pipeline_link for all
  using (auth.role() = 'service_role')
  with check (auth.role() = 'service_role');
