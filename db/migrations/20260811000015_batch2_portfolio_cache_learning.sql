-- Provider-neutral persistence for Batch 2 portfolio-derived state.
-- Tenant filtering is explicit in repository queries; Supabase RLS is not part
-- of the portable runtime contract.

create table if not exists public.portfolio_feed_cache (
  id uuid primary key default gen_random_uuid(),
  user_id text not null,
  cached_at double precision not null,
  items jsonb not null default '[]',
  created_at timestamptz not null default timezone('utc', now())
);
create index if not exists portfolio_feed_cache_user_id_idx
  on public.portfolio_feed_cache (user_id);

create table if not exists public.portfolio_rejection_patterns (
  id uuid primary key default gen_random_uuid(),
  user_id text not null,
  stats jsonb not null default '{}',
  created_at timestamptz not null default timezone('utc', now())
);
create index if not exists portfolio_rejection_patterns_user_id_idx
  on public.portfolio_rejection_patterns (user_id);

create table if not exists public.portfolio_agent_metrics (
  id text not null,
  data jsonb not null default '{}',
  created_at timestamptz not null default timezone('utc', now()),
  user_id text not null default 'default',
  primary key (user_id, id)
);
create index if not exists portfolio_agent_metrics_user_id_idx
  on public.portfolio_agent_metrics (user_id);
