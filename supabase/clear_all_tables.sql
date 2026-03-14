-- Clear all Aethria table data (keeps tables). Run in Supabase Dashboard → SQL Editor.
-- After running, restart agents so they fill with the right user_id.

truncate table public.startups cascade;
truncate table public.portfolio_decisions cascade;
truncate table public.portfolio_positions cascade;
truncate table public.portfolio_rejections cascade;
truncate table public.portfolio_watchlist cascade;
truncate table public.portfolio_signals cascade;
truncate table public.portfolio_agent_metrics cascade;
truncate table public.meta_mutation_log cascade;
truncate table public.meta_reports cascade;
truncate table public.portfolio_budgets cascade;
truncate table public.memory cascade;
truncate table public.settings cascade;
truncate table public.serp_usage cascade;
truncate table public.analytics_sector_concentration cascade;
truncate table public.meta_prompt_library cascade;
truncate table public.meta_scout_weights cascade;
truncate table public.meta_calibration_state cascade;
truncate table public.meta_cycle_counters cascade;
