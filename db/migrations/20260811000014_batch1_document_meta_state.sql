-- Provider-neutral Batch 1 document and Meta-state contract.
create table if not exists public.analytics_sector_concentration (
  user_id text not null,
  key text not null,
  data jsonb not null default '{}'::jsonb,
  primary key (user_id, key)
);
create table if not exists public.portfolio_budgets (
  user_id text not null,
  key text not null,
  data jsonb not null default '{}'::jsonb,
  primary key (user_id, key)
);
create table if not exists public.meta_prompt_library (
  user_id text not null,
  key text not null,
  data jsonb not null default '{}'::jsonb,
  primary key (user_id, key)
);
create table if not exists public.meta_scout_weights (
  user_id text not null,
  key text not null,
  data jsonb not null default '{}'::jsonb,
  primary key (user_id, key)
);
create table if not exists public.meta_calibration_state (
  user_id text not null,
  key text not null,
  data jsonb not null default '{}'::jsonb,
  primary key (user_id, key)
);
create table if not exists public.meta_cycle_counters (
  user_id text not null,
  key text not null,
  data jsonb not null default '{}'::jsonb,
  primary key (user_id, key)
);
create table if not exists public.meta_churn_signals (
  user_id text not null,
  key text not null,
  data jsonb not null default '{}'::jsonb,
  primary key (user_id, key)
);

create table if not exists public.meta_mutation_log (
  user_id text not null,
  id text not null,
  data jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default timezone('utc', now()),
  primary key (user_id, id)
);
create table if not exists public.meta_reports (
  user_id text not null,
  id text not null,
  data jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default timezone('utc', now()),
  primary key (user_id, id)
);

create index if not exists meta_mutation_log_tenant_created_idx
  on public.meta_mutation_log (user_id, created_at);
create index if not exists meta_reports_tenant_created_idx
  on public.meta_reports (user_id, created_at);
create index if not exists meta_churn_signals_tenant_idx
  on public.meta_churn_signals (user_id);

-- Counter increments are serialized in PostgreSQL rather than read-modify-write in Python.
create or replace function public.increment_meta_cycle_counter(
  p_user_id text,
  p_key text default 'default'
) returns integer
language sql
security invoker
set search_path = public
as $$
  insert into public.meta_cycle_counters (user_id, key, data)
  values (p_user_id, p_key, '{"value": 1}'::jsonb)
  on conflict (user_id, key) do update
    set data = jsonb_build_object(
      'value', coalesce(nullif(public.meta_cycle_counters.data ->> 'value', '')::integer, 0) + 1
    )
  returning (data ->> 'value')::integer
$$;
