-- Aethria: JSON-backed tables (portfolio, memory, settings, meta, analytics).
-- Service role only; no RLS. Run in Supabase SQL Editor or: supabase db push

-- List tables: one row per record, id + data (jsonb), ordered by created_at
create table if not exists public.portfolio_decisions (
  id text primary key,
  data jsonb not null,
  created_at timestamptz not null default timezone('utc', now())
);
create table if not exists public.portfolio_positions (
  id text primary key,
  data jsonb not null,
  created_at timestamptz not null default timezone('utc', now())
);
create table if not exists public.portfolio_rejections (
  id text primary key,
  data jsonb not null,
  created_at timestamptz not null default timezone('utc', now())
);
create table if not exists public.portfolio_watchlist (
  id text primary key,
  data jsonb not null,
  created_at timestamptz not null default timezone('utc', now())
);
create table if not exists public.portfolio_signals (
  id text primary key,
  data jsonb not null,
  created_at timestamptz not null default timezone('utc', now())
);
create table if not exists public.portfolio_agent_metrics (
  id text primary key,
  data jsonb not null,
  created_at timestamptz not null default timezone('utc', now())
);
create table if not exists public.meta_mutation_log (
  id text primary key,
  data jsonb not null,
  created_at timestamptz not null default timezone('utc', now())
);
create table if not exists public.meta_reports (
  id text primary key,
  data jsonb not null,
  created_at timestamptz not null default timezone('utc', now())
);

-- Doc tables: key + data (jsonb), single row per logical document
create table if not exists public.portfolio_budgets (
  key text primary key,
  data jsonb not null
);
create table if not exists public.memory (
  key text primary key,
  data jsonb not null
);
create table if not exists public.settings (
  key text primary key,
  data jsonb not null
);
create table if not exists public.serp_usage (
  key text primary key,
  data jsonb not null
);
create table if not exists public.analytics_sector_concentration (
  key text primary key,
  data jsonb not null
);
create table if not exists public.meta_prompt_library (
  key text primary key,
  data jsonb not null
);
create table if not exists public.meta_scout_weights (
  key text primary key,
  data jsonb not null
);
create table if not exists public.meta_calibration_state (
  key text primary key,
  data jsonb not null
);
create table if not exists public.meta_cycle_counters (
  key text primary key,
  data jsonb not null
);
