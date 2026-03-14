-- Fix schema mismatch: drop existing tables and recreate with (key, data) or (id, data, created_at).
-- Run this in Supabase SQL Editor if you see "column X.key does not exist" or "column X.data does not exist".
-- WARNING: This deletes all data in these tables.

-- Doc tables
drop table if exists public.memory cascade;
drop table if exists public.settings cascade;
drop table if exists public.serp_usage cascade;
drop table if exists public.analytics_sector_concentration cascade;
drop table if exists public.meta_prompt_library cascade;
drop table if exists public.meta_scout_weights cascade;
drop table if exists public.meta_calibration_state cascade;
drop table if exists public.meta_cycle_counters cascade;
drop table if exists public.portfolio_budgets cascade;

-- List tables
drop table if exists public.portfolio_decisions cascade;
drop table if exists public.portfolio_positions cascade;
drop table if exists public.portfolio_rejections cascade;
drop table if exists public.portfolio_watchlist cascade;
drop table if exists public.portfolio_signals cascade;
drop table if exists public.portfolio_agent_metrics cascade;
drop table if exists public.meta_mutation_log cascade;
drop table if exists public.meta_reports cascade;

-- Recreate with correct schema

-- List tables: id + data + created_at
create table public.portfolio_decisions (
  id text primary key,
  data jsonb not null,
  created_at timestamptz not null default timezone('utc', now())
);
create table public.portfolio_positions (
  id text primary key,
  data jsonb not null,
  created_at timestamptz not null default timezone('utc', now())
);
create table public.portfolio_rejections (
  id text primary key,
  data jsonb not null,
  created_at timestamptz not null default timezone('utc', now())
);
create table public.portfolio_watchlist (
  id text primary key,
  data jsonb not null,
  created_at timestamptz not null default timezone('utc', now())
);
create table public.portfolio_signals (
  id text primary key,
  data jsonb not null,
  created_at timestamptz not null default timezone('utc', now())
);
create table public.portfolio_agent_metrics (
  id text primary key,
  data jsonb not null,
  created_at timestamptz not null default timezone('utc', now())
);
create table public.meta_mutation_log (
  id text primary key,
  data jsonb not null,
  created_at timestamptz not null default timezone('utc', now())
);
create table public.meta_reports (
  id text primary key,
  data jsonb not null,
  created_at timestamptz not null default timezone('utc', now())
);

-- Doc tables: key + data
create table public.portfolio_budgets (
  key text primary key,
  data jsonb not null
);
create table public.memory (
  key text primary key,
  data jsonb not null
);
create table public.settings (
  key text primary key,
  data jsonb not null
);
create table public.serp_usage (
  key text primary key,
  data jsonb not null
);
create table public.analytics_sector_concentration (
  key text primary key,
  data jsonb not null
);
create table public.meta_prompt_library (
  key text primary key,
  data jsonb not null
);
create table public.meta_scout_weights (
  key text primary key,
  data jsonb not null
);
create table public.meta_calibration_state (
  key text primary key,
  data jsonb not null
);
create table public.meta_cycle_counters (
  key text primary key,
  data jsonb not null
);
