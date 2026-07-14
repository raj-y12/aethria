from types import SimpleNamespace

from models import ScoutInfo
from supabase_storage import SupabaseStartupsStorage


class _Query:
    def __init__(self, store):
        self.store = store
        self.filters = {}
        self.operation = "select"

    def select(self, *args, **kwargs):
        self.operation = "select"
        return self

    def eq(self, column, value):
        self.filters[column] = value
        return self

    def ilike(self, column, value):
        self.filters[f"ilike:{column}"] = value
        return self

    def limit(self, *args, **kwargs):
        return self

    def upsert(self, payload, *args, **kwargs):
        self.operation = "upsert"
        self.store["upserts"].append(payload)
        return self

    def execute(self):
        if self.operation == "upsert":
            return SimpleNamespace(data=[])
        if self.filters.get("startup_id") == "new-unused-id":
            return SimpleNamespace(data=[])
        if str(self.filters.get("ilike:display_name") or "").lower() == "acme":
            return SimpleNamespace(
                data=[{"startup_id": "existing-startup", "display_name": "Acme"}]
            )
        return SimpleNamespace(data=[])


class _Client:
    def __init__(self):
        self.store = {"upserts": []}

    def table(self, name):
        return _Query(self.store)


def test_duplicate_company_name_returns_existing_supabase_startup_id():
    client = _Client()
    storage = SupabaseStartupsStorage(client, "user-1")
    scout = ScoutInfo(
        startup_id="new-unused-id",
        name="acme",
        one_line="Factory intelligence",
        sector="Industrial AI",
        problem="Fragmented systems",
        solution="Unified data layer",
        target_users="Factories",
        why_now="Edge inference",
        scout_type="market_driven",
        confidence_score=0.8,
        references=["https://acme.example"],
    )

    assert storage.add_startup(scout) == "existing-startup"
    assert client.store["upserts"] == []


def test_normalized_company_name_migration_enforces_tenant_uniqueness():
    from pathlib import Path

    sql = (
        Path(__file__).parents[2]
        / "supabase/migrations/20260714192642_startups_normalized_name_unique.sql"
    ).read_text().lower()

    assert "unique index" in sql
    assert "user_id, lower(btrim(display_name))" in sql
    assert "duplicate normalized startup names" in sql
