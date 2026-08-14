import pytest

from portfolio.store import PortfolioStore


def _canonical_row(startup_id="canonical-1"):
    return {
        "startup_id": startup_id,
        "scout_info": {
            "name": "Canonical Co",
            "one_line": "A useful company",
            "sector": "SaaS",
            "problem": "Manual work",
            "solution": "Automation",
            "target_users": "Funds",
            "why_now": "Now",
            "scout_type": "market_driven",
            "confidence_score": 0.8,
            "discovered_at": "2026-08-11T00:00:00+00:00",
        },
        "financials": {},
        "version": 3,
        "first_seen_at": "2026-08-11T00:00:00+00:00",
        "created_at": "2026-08-11T00:00:00+00:00",
        "updated_at": "2026-08-11T00:00:00+00:00",
    }


def test_portfolio_store_projects_canonical_and_legacy_ids(monkeypatch, tmp_path):
    monkeypatch.delenv("USE_SUPABASE_STORAGE", raising=False)
    store = PortfolioStore(
        data_dir=str(tmp_path / "portfolio"),
        canonical_startups=[_canonical_row()],
        legacy_startup_aliases={"legacy-1": "canonical-1"},
    )

    canonical = store.get_startup("canonical-1")
    legacy = store.get_startup("legacy-1")

    assert canonical == legacy
    assert canonical["id"] == "canonical-1"
    assert canonical["startup_id"] == "canonical-1"
    assert canonical["name"] == "Canonical Co"
    assert canonical["problem"] == "Manual work"
    assert canonical["scout_confidence"] == 0.8
    assert store.get_all_startups() == [canonical]


def test_portfolio_store_does_not_create_startups_from_reduced_records(monkeypatch, tmp_path):
    monkeypatch.delenv("USE_SUPABASE_STORAGE", raising=False)
    store = PortfolioStore(data_dir=str(tmp_path / "portfolio"))

    assert store.add_startup({"id": "new-legacy", "name": "Never Persist"}) == "new-legacy"
    assert store.get_all_startups() == []


def test_missing_alias_and_wrong_tenant_are_not_resolved(monkeypatch, tmp_path):
    monkeypatch.delenv("USE_SUPABASE_STORAGE", raising=False)
    store = PortfolioStore(
        data_dir=str(tmp_path / "portfolio"),
        user_id="tenant-a",
        canonical_startups=[_canonical_row()],
        legacy_startup_aliases={"legacy-1": "canonical-1"},
    )

    assert store.get_startup("unknown-legacy") is None
    assert store.get_startup("canonical-2") is None
