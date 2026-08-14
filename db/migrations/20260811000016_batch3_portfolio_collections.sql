-- Provider-neutral persistence for the five legacy portfolio collections.

create table if not exists public.portfolio_decisions (
  id text not null,
  data jsonb not null default '{}',
  created_at timestamptz not null default timezone('utc', now()),
  user_id text not null default 'default',
  primary key (user_id, id)
);
create index if not exists portfolio_decisions_user_id_idx on public.portfolio_decisions (user_id);

create table if not exists public.portfolio_positions (
  id text not null,
  data jsonb not null default '{}',
  created_at timestamptz not null default timezone('utc', now()),
  user_id text not null default 'default',
  primary key (user_id, id)
);
create index if not exists portfolio_positions_user_id_idx on public.portfolio_positions (user_id);

create table if not exists public.portfolio_rejections (
  id text not null,
  data jsonb not null default '{}',
  created_at timestamptz not null default timezone('utc', now()),
  user_id text not null default 'default',
  primary key (user_id, id)
);
create index if not exists portfolio_rejections_user_id_idx on public.portfolio_rejections (user_id);

create table if not exists public.portfolio_watchlist (
  id text not null,
  data jsonb not null default '{}',
  created_at timestamptz not null default timezone('utc', now()),
  user_id text not null default 'default',
  primary key (user_id, id)
);
create index if not exists portfolio_watchlist_user_id_idx on public.portfolio_watchlist (user_id);

create table if not exists public.portfolio_signals (
  id text not null,
  data jsonb not null default '{}',
  created_at timestamptz not null default timezone('utc', now()),
  user_id text not null default 'default',
  primary key (user_id, id)
);
create index if not exists portfolio_signals_user_id_idx on public.portfolio_signals (user_id);
