-- Tables that backend/portfolio/store.py, backend/utils/feed_fetcher.py, and
-- backend/portfolio/rejection.py have always required but no prior migration
-- created — fresh schemas were silently falling back to local files even in
-- production. Service-role-only, matching the other legacy tenant tables.

create table if not exists public.portfolio_startups (
  id text primary key,
  user_id text not null,
  startup_id text not null,
  name text not null default '',
  one_line text not null default '',
  sector text not null default '',
  problem text not null default '',
  solution text not null default '',
  target_users text not null default '',
  why_now text not null default '',
  scout_type text not null default '',
  scout_confidence double precision not null default 0,
  discovered_at timestamptz not null default timezone('utc', now()),
  version integer not null default 1,
  metadata jsonb not null default '{}'
);
create index if not exists portfolio_startups_user_id_idx on public.portfolio_startups (user_id);
create index if not exists portfolio_startups_user_startup_idx on public.portfolio_startups (user_id, startup_id);

create table if not exists public.portfolio_feed_cache (
  id text primary key,
  user_id text not null,
  cached_at double precision not null,
  items jsonb not null default '[]',
  created_at timestamptz not null default timezone('utc', now())
);
create index if not exists portfolio_feed_cache_user_id_idx on public.portfolio_feed_cache (user_id);

create table if not exists public.portfolio_rejection_patterns (
  id text primary key,
  user_id text not null,
  stats jsonb not null default '{}',
  created_at timestamptz not null default timezone('utc', now())
);
create index if not exists portfolio_rejection_patterns_user_id_idx on public.portfolio_rejection_patterns (user_id);

do $$
declare
  t text;
  new_tables text[] := array[
    'portfolio_startups', 'portfolio_feed_cache', 'portfolio_rejection_patterns'
  ];
begin
  foreach t in array new_tables loop
    execute format('alter table public.%I enable row level security', t);
    execute format('drop policy if exists %I on public.%I', t || '_service_role_all', t);
    execute format(
      'create policy %I on public.%I for all to service_role using (true) with check (true)',
      t || '_service_role_all', t
    );
    execute format('revoke all on table public.%I from public, anon, authenticated', t);
    execute format('grant select, insert, update, delete on table public.%I to service_role', t);
  end loop;
end $$;
