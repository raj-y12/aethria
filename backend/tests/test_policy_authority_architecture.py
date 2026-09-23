from pathlib import Path


BACKEND = Path(__file__).resolve().parents[1]


def _source(relative: str) -> str:
    return (BACKEND / relative).read_text(encoding="utf-8")


def test_normal_policy_paths_use_governed_repository_only():
    prerequisites = _source("evaluation_v2/prerequisites.py")
    outbox = _source("jobs/outbox.py")
    analysis = _source("investment_analysis/repository.py")
    policy_upgrade = _source("services/scoring/policy_upgrade.py")

    assert "get_active_published_policy" in prerequisites
    assert "fund_policy_versions" not in prerequisites
    assert "publish_policy" not in outbox
    assert "fund_policy_versions" not in outbox
    assert "fund_policy_versions" not in analysis
    assert 'rpc("upgrade_fund_policy"' not in policy_upgrade


def test_legacy_policy_persistence_is_fenced_to_compatibility_modules():
    policy_store = _source("services/scoring/policy_store.py")
    compatibility = _source("services/scoring/legacy_policy_compat.py")
    cli = _source("scripts/upgrade_published_policy.py")

    assert "LEGACY" in policy_store or "legacy" in policy_store.lower()
    assert "fund_policy_versions" in policy_store
    assert "upgrade_fund_policy" in compatibility
    assert "legacy" in cli.lower()
