-- Add missing 'data' (and list 'created_at') columns to existing tables.
-- Run if you see "column X.data does not exist". Safe to run multiple times.

-- Doc tables: ensure 'data' exists
alter table if exists public.memory add column if not exists data jsonb default '{}';
alter table if exists public.settings add column if not exists data jsonb default '{}';
alter table if exists public.serp_usage add column if not exists data jsonb default '{}';
alter table if exists public.analytics_sector_concentration add column if not exists data jsonb default '{}';
alter table if exists public.meta_prompt_library add column if not exists data jsonb default '{}';
alter table if exists public.meta_scout_weights add column if not exists data jsonb default '{}';
alter table if exists public.meta_calibration_state add column if not exists data jsonb default '{}';
alter table if exists public.meta_cycle_counters add column if not exists data jsonb default '{}';
alter table if exists public.portfolio_budgets add column if not exists data jsonb default '{}';

-- List tables: ensure 'data' and 'created_at' exist
alter table if exists public.portfolio_decisions add column if not exists data jsonb default '{}';
alter table if exists public.portfolio_decisions add column if not exists created_at timestamptz default timezone('utc', now());
alter table if exists public.portfolio_positions add column if not exists data jsonb default '{}';
alter table if exists public.portfolio_positions add column if not exists created_at timestamptz default timezone('utc', now());
alter table if exists public.portfolio_rejections add column if not exists data jsonb default '{}';
alter table if exists public.portfolio_rejections add column if not exists created_at timestamptz default timezone('utc', now());
alter table if exists public.portfolio_watchlist add column if not exists data jsonb default '{}';
alter table if exists public.portfolio_watchlist add column if not exists created_at timestamptz default timezone('utc', now());
alter table if exists public.portfolio_signals add column if not exists data jsonb default '{}';
alter table if exists public.portfolio_signals add column if not exists created_at timestamptz default timezone('utc', now());
alter table if exists public.portfolio_agent_metrics add column if not exists data jsonb default '{}';
alter table if exists public.portfolio_agent_metrics add column if not exists created_at timestamptz default timezone('utc', now());
alter table if exists public.meta_mutation_log add column if not exists data jsonb default '{}';
alter table if exists public.meta_mutation_log add column if not exists created_at timestamptz default timezone('utc', now());
alter table if exists public.meta_reports add column if not exists data jsonb default '{}';
alter table if exists public.meta_reports add column if not exists created_at timestamptz default timezone('utc', now());
