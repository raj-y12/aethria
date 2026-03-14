-- =============================================================================
-- Aethria Supabase schema — full schema from backend (single source of truth)
-- =============================================================================
-- Backend: supabase_storage.py (startups), supabase_doc_store.py (list/doc tables).
-- Run this entire file in Supabase Dashboard → SQL Editor.
-- WARNING: Drops and recreates all tables below; any existing data is lost.
-- =============================================================================

-- Drop all Aethria tables (order can matter for FKs; we have none between these)
drop table if exists public.startups cascade;
drop table if exists public.memory cascade;
drop table if exists public.settings cascade;
drop table if exists public.serp_usage cascade;
drop table if exists public.analytics_sector_concentration cascade;
drop table if exists public.meta_prompt_library cascade;
drop table if exists public.meta_scout_weights cascade;
drop table if exists public.meta_calibration_state cascade;
drop table if exists public.meta_cycle_counters cascade;
drop table if exists public.portfolio_budgets cascade;
drop table if exists public.portfolio_decisions cascade;
drop table if exists public.portfolio_positions cascade;
drop table if exists public.portfolio_rejections cascade;
drop table if exists public.portfolio_watchlist cascade;
drop table if exists public.portfolio_signals cascade;
drop table if exists public.portfolio_agent_metrics cascade;
drop table if exists public.meta_mutation_log cascade;
drop table if exists public.meta_reports cascade;

-- -----------------------------------------------------------------------------
-- Startups (supabase_storage.py: SupabaseStartupsStorage)
-- Per-user pipeline; API uses service_role + request.state.user_id for filtering.
-- -----------------------------------------------------------------------------
create table public.startups (
  id uuid primary key default gen_random_uuid(),
  user_id text not null,
  startup_id text not null,
  scout_info jsonb not null,
  review_info jsonb,
  partner_info jsonb,
  financials jsonb not null,
  version integer not null default 1,
  human_resolution jsonb,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);
create unique index startups_user_startup_id_idx on public.startups (user_id, startup_id);
create index startups_user_id_idx on public.startups (user_id);
create index startups_scout_info_gin_idx on public.startups using gin (scout_info);
create index startups_review_info_gin_idx on public.startups using gin (review_info);
create index startups_partner_info_gin_idx on public.startups using gin (partner_info);
alter table public.startups enable row level security;
drop policy if exists "Users manage own startups" on public.startups;
create policy "Users manage own startups"
  on public.startups for all
  using (auth.jwt() ->> 'sub' = user_id)
  with check (auth.jwt() ->> 'sub' = user_id);
drop policy if exists "Service role full access startups" on public.startups;
create policy "Service role full access startups"
  on public.startups for all
  using (auth.role() = 'service_role')
  with check (auth.role() = 'service_role');

-- -----------------------------------------------------------------------------
-- List tables (supabase_doc_store: list_get_all, list_upsert, list_append_only)
-- Columns: id (PK), data (jsonb), created_at (default now)
-- -----------------------------------------------------------------------------
create table public.portfolio_decisions (
  id text primary key,
  data jsonb not null default '{}',
  created_at timestamptz not null default timezone('utc', now())
);
create table public.portfolio_positions (
  id text primary key,
  data jsonb not null default '{}',
  created_at timestamptz not null default timezone('utc', now())
);
create table public.portfolio_rejections (
  id text primary key,
  data jsonb not null default '{}',
  created_at timestamptz not null default timezone('utc', now())
);
create table public.portfolio_watchlist (
  id text primary key,
  data jsonb not null default '{}',
  created_at timestamptz not null default timezone('utc', now())
);
create table public.portfolio_signals (
  id text primary key,
  data jsonb not null default '{}',
  created_at timestamptz not null default timezone('utc', now())
);
create table public.portfolio_agent_metrics (
  id text primary key,
  data jsonb not null default '{}',
  created_at timestamptz not null default timezone('utc', now())
);
create table public.meta_mutation_log (
  id text primary key,
  data jsonb not null default '{}',
  created_at timestamptz not null default timezone('utc', now())
);
create table public.meta_reports (
  id text primary key,
  data jsonb not null default '{}',
  created_at timestamptz not null default timezone('utc', now())
);

-- -----------------------------------------------------------------------------
-- Doc tables (supabase_doc_store: doc_get, doc_set, doc_get_int, doc_set_int)
-- Columns: key (PK), data (jsonb)
-- -----------------------------------------------------------------------------
create table public.portfolio_budgets (
  key text primary key,
  data jsonb not null default '{}'
);
create table public.memory (
  key text primary key,
  data jsonb not null default '{}'
);
create table public.settings (
  key text primary key,
  data jsonb not null default '{}'
);
create table public.serp_usage (
  key text primary key,
  data jsonb not null default '{}'
);
create table public.analytics_sector_concentration (
  key text primary key,
  data jsonb not null default '{}'
);
create table public.meta_prompt_library (
  key text primary key,
  data jsonb not null default '{}'
);
create table public.meta_scout_weights (
  key text primary key,
  data jsonb not null default '{}'
);
create table public.meta_calibration_state (
  key text primary key,
  data jsonb not null default '{}'
);
create table public.meta_cycle_counters (
  key text primary key,
  data jsonb not null default '{}'
);

-- Ensure PostgREST exposes these (public schema is default; no RLS on these tables, service_role used by backend)
