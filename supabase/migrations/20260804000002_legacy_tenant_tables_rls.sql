-- Enable RLS on legacy doc/list/meta tables that predate tenant scoping.
-- These are read and written only by the backend service-role client
-- (frontend never touches Supabase directly, per AGENTS.md); no policy
-- exists here for the anon/authenticated PostgREST roles.

do $$
declare
  t text;
  legacy_tenant_tables text[] := array[
    'portfolio_budgets', 'memory', 'settings', 'serp_usage',
    'analytics_sector_concentration', 'meta_prompt_library', 'meta_scout_weights',
    'meta_calibration_state', 'meta_cycle_counters',
    'portfolio_decisions', 'portfolio_positions', 'portfolio_rejections',
    'portfolio_watchlist', 'portfolio_signals', 'portfolio_agent_metrics',
    'meta_mutation_log', 'meta_reports',
    'meta_churn_signals', 'pipeline_activity', 'user_state'
  ];
begin
  foreach t in array legacy_tenant_tables loop
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
