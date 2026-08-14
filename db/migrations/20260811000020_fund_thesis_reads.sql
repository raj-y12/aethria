-- Provider-neutral fund-thesis read contract.
-- Supabase platform policies, roles, grants, and RPCs are intentionally absent.

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
  version_number integer not null,
  raw_text text not null default '',
  parsed_json jsonb not null default '{}'::jsonb,
  is_active boolean not null default false,
  created_at timestamptz not null default timezone('utc', now()),
  constraint fund_thesis_versions_thesis_version_unique
    unique (thesis_id, version_number),
  constraint fund_thesis_versions_user_id_unique unique (user_id, id)
);

create index if not exists fund_thesis_versions_user_id_idx
  on public.fund_thesis_versions (user_id);
create index if not exists fund_thesis_versions_thesis_id_idx
  on public.fund_thesis_versions (thesis_id);
create unique index if not exists fund_thesis_versions_one_active_idx
  on public.fund_thesis_versions (thesis_id)
  where is_active;

alter table public.fund_thesis
  add constraint fund_thesis_active_version_tenant_fk
  foreign key (user_id, active_version_id)
  references public.fund_thesis_versions (user_id, id)
  deferrable initially deferred;

create table if not exists public.fund_thesis_embeddings (
  id uuid primary key default gen_random_uuid(),
  user_id text not null,
  version_id uuid not null,
  embedding_vector jsonb not null default '[]'::jsonb,
  model text not null default 'text-embedding-3-small',
  created_at timestamptz not null default timezone('utc', now()),
  constraint fund_thesis_embeddings_version_fk
    foreign key (user_id, version_id)
    references public.fund_thesis_versions (user_id, id)
    on delete cascade,
  constraint fund_thesis_embeddings_version_unique unique (version_id)
);

create index if not exists fund_thesis_embeddings_user_id_idx
  on public.fund_thesis_embeddings (user_id);

create table if not exists public.fund_thesis_pipeline_link (
  id uuid primary key default gen_random_uuid(),
  user_id text not null,
  thesis_version_id uuid not null,
  pipeline_run_id uuid,
  affected_startups_count integer not null default 0,
  created_at timestamptz not null default timezone('utc', now()),
  constraint fund_thesis_pipeline_link_version_fk
    foreign key (user_id, thesis_version_id)
    references public.fund_thesis_versions (user_id, id)
    on delete cascade
);

create index if not exists fund_thesis_pipeline_link_user_idx
  on public.fund_thesis_pipeline_link (user_id);
create index if not exists fund_thesis_pipeline_link_version_idx
  on public.fund_thesis_pipeline_link (thesis_version_id);
