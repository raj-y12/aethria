#!/usr/bin/env python3
"""
Clear all rows from Aethria Supabase tables so they can refill with the right data.
Uses SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY from .env (load from repo root).

Run from repo root: python3 backend/scripts/clear_supabase_tables.py
Or from backend: python3 scripts/clear_supabase_tables.py (after loading parent .env)
"""
import os
import sys
from pathlib import Path

# Load .env from repo root
repo_root = Path(__file__).resolve().parent.parent.parent
env_file = repo_root / ".env"
if env_file.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(env_file)
    except ImportError:
        pass

# Backend on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from supabase_client import get_service_client

# Clear cache so we use env we just loaded
get_service_client.cache_clear()

TABLES_WITH_ID = [
    "startups",
    "portfolio_decisions",
    "portfolio_positions",
    "portfolio_rejections",
    "portfolio_watchlist",
    "portfolio_signals",
    "portfolio_agent_metrics",
    "meta_mutation_log",
    "meta_reports",
]

TABLES_WITH_KEY = [
    "portfolio_budgets",
    "memory",
    "settings",
    "serp_usage",
    "analytics_sector_concentration",
    "meta_prompt_library",
    "meta_scout_weights",
    "meta_calibration_state",
    "meta_cycle_counters",
]


def main():
    client = get_service_client()
    for table in TABLES_WITH_ID:
        try:
            # Match all rows: id != sentinel (startups use uuid; list tables use text id)
            if table == "startups":
                r = client.table(table).delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
            else:
                r = client.table(table).delete().neq("id", "").execute()
            print(f"  {table}: cleared")
        except Exception as e:
            print(f"  {table}: error — {e}")
    for table in TABLES_WITH_KEY:
        try:
            client.table(table).delete().neq("key", "").execute()
            print(f"  {table}: cleared")
        except Exception as e:
            print(f"  {table}: error — {e}")
    print("Done. Restart agents (python3 run.py) so they fill with the right data.")


if __name__ == "__main__":
    main()
