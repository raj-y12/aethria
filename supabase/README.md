# Aethria Supabase migrations

Schema is driven by the backend:

- **Startups:** `backend/supabase_storage.py` → table `startups` (user_id, startup_id, scout_info, review_info, partner_info, financials, …)
- **Doc/list tables:** `backend/supabase_doc_store.py` → list tables `(id, data, created_at)`, doc tables `(key, data)`

## Apply (full schema in one file)

1. Open **Supabase Dashboard → SQL Editor**.
2. Run **`migrations/20260314000005_aethria_tables_from_code.sql`** in full.

That migration drops and recreates every Aethria table so the schema matches the code:

- **startups** — pipeline per user (RLS + service role policy)
- **portfolio_decisions, portfolio_positions, portfolio_rejections, portfolio_watchlist, portfolio_signals, portfolio_agent_metrics** — list tables
- **meta_mutation_log, meta_reports** — list tables
- **memory, settings, serp_usage, analytics_sector_concentration, meta_prompt_library, meta_scout_weights, meta_calibration_state, meta_cycle_counters, portfolio_budgets** — doc tables

Use **SUPABASE_SERVICE_ROLE_KEY** in the backend for API and agents.

## Clear all table data

To wipe rows and refill with the right data (e.g. after fixing `AETHRIA_DEFAULT_USER_ID`):

- **SQL:** In Supabase Dashboard → SQL Editor, run **`clear_all_tables.sql`**.
- **Python:** From repo root: `python3 backend/scripts/clear_supabase_tables.py` (uses `.env`). Then restart `python3 run.py`.
