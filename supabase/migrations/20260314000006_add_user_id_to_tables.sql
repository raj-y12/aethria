-- =============================================================================
-- Add user_id to all doc and list tables for multi-tenant data
-- =============================================================================
-- Existing rows get user_id = 'default' so single-tenant data keeps working.
-- Backend must pass user_id (or use run context) for all doc/list operations.
-- =============================================================================

-- ---- Doc tables: add user_id, switch PK to (user_id, key) ----
do $$
declare
  t text;
  doc_tables text[] := array[
    'portfolio_budgets', 'memory', 'settings', 'serp_usage',
    'analytics_sector_concentration', 'meta_prompt_library', 'meta_scout_weights',
    'meta_calibration_state', 'meta_cycle_counters'
  ];
begin
  foreach t in array doc_tables loop
    execute format('alter table public.%I add column if not exists user_id text not null default ''default''', t);
    execute format('alter table public.%I drop constraint if exists %I', t, t || '_pkey');
    execute format('alter table public.%I add primary key (user_id, key)', t);
    execute format('create index if not exists %I on public.%I (user_id)', t || '_user_id_idx', t);
  end loop;
end $$;

-- ---- List tables: add user_id, switch PK to (user_id, id) ----
do $$
declare
  t text;
  list_tables text[] := array[
    'portfolio_decisions', 'portfolio_positions', 'portfolio_rejections',
    'portfolio_watchlist', 'portfolio_signals', 'portfolio_agent_metrics',
    'meta_mutation_log', 'meta_reports'
  ];
begin
  foreach t in array list_tables loop
    execute format('alter table public.%I add column if not exists user_id text not null default ''default''', t);
    execute format('alter table public.%I drop constraint if exists %I', t, t || '_pkey');
    execute format('alter table public.%I add primary key (user_id, id)', t);
    execute format('create index if not exists %I on public.%I (user_id)', t || '_user_id_idx', t);
  end loop;
end $$;
