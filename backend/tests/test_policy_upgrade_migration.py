from pathlib import Path


MIGRATION = (
    Path(__file__).parents[2]
    / "supabase/migrations/20260721143000_patch_upgrade_fund_policy_settings.sql"
)


def test_policy_upgrade_rpc_is_atomic_compare_and_swap_and_service_role_only():
    sql = MIGRATION.read_text().lower()

    assert "create or replace function public.upgrade_fund_policy" in sql
    assert "pg_advisory_xact_lock" in sql
    assert "for update" in sql
    assert "p_expected_policy_id" in sql
    assert "p_expected_policy_hash" in sql
    assert "raise exception" in sql
    assert "insert into public.fund_policy_versions" in sql
    assert "on conflict (user_id, id) do nothing" in sql
    assert "update public.settings" in sql
    assert "jsonb_set" in sql
    assert "v_current_settings" in sql
    assert "coalesce(v_current_settings -> 'fund_config', '{}'::jsonb)" in sql
    assert "set data = p_settings_data" not in sql
    assert "activepolicyversionid" in sql
    assert "publishedpolicyhash" in sql
    assert "draftpolicyhash" in sql
    assert "lastpublishedat" in sql
    assert "where user_id = p_user_id" in sql
    assert "and key = p_user_id" in sql
    assert "revoke all on function public.upgrade_fund_policy" in sql
    assert "grant execute on function public.upgrade_fund_policy" in sql
    assert "to service_role" in sql
    assert "to anon" not in sql
    assert "to authenticated" not in sql


def test_policy_upgrade_migration_is_required_by_readiness_ledger():
    from scripts import check_phase8_readiness as readiness

    assert readiness.POLICY_UPGRADE_MIGRATION == MIGRATION.name
    assert readiness._policy_upgrade_migration_file_check()["status"] == "passed"
    check = readiness._policy_upgrade_version_check(set())
    assert check["status"] == "failed"
    assert check["missing"] == ["20260721143000"]
