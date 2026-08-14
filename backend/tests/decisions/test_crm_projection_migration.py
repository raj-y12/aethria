from pathlib import Path


def test_external_mapping_migration_has_provider_workspace_and_tenant_boundaries():
    sql = Path("supabase/migrations/20260812000004_external_entity_mappings.sql").read_text().lower()
    assert "create table if not exists public.external_entity_mappings" in sql
    for value in ("user_id", "provider", "entity_type", "aethria_entity_id", "external_entity_id", "workspace_id", "sync_status", "last_synced_at"):
        assert value in sql
    assert "unique (user_id, provider, workspace_id, entity_type, aethria_entity_id)" in sql
    assert "unique (user_id, provider, workspace_id, entity_type, external_entity_id)" in sql
    assert "row level security" in sql
