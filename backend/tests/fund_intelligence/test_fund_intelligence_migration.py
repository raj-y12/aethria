from pathlib import Path


MIGRATION = Path(__file__).parents[3] / "supabase/migrations/20260715270000_fund_intelligence.sql"


def test_fund_intelligence_schema_is_attributed_versioned_and_governed():
    sql = MIGRATION.read_text().lower()
    assert "create table if not exists public.learning_signals" in sql
    assert "create table if not exists public.policy_proposals" in sql
    assert "create table if not exists public.policy_impact_previews" in sql
    assert "create table if not exists public.governed_policy_versions" in sql
    assert "sample_size" in sql
    assert "limitations" in sql
    assert "published_by" in sql
    assert "alter table public.policy_proposals enable row level security" in sql


def test_proposal_status_has_no_automatic_active_state():
    sql = MIGRATION.read_text().lower()
    assert "auto_activate" not in sql
    assert "status in ('draft','ready_for_review','accepted','edited_and_accepted','rejected','deferred','expired')" in sql


def test_review_fix_migration_binds_governed_version_to_policy_hash():
    review_fix = Path(__file__).parents[3] / "supabase/migrations/20260716090000_review_fixes.sql"
    sql = review_fix.read_text().lower()
    assert "add column if not exists policy_hash text" in sql
