import pytest

from scripts.verify_local_snapshot import validate_snapshot_facts


def _manifest():
    return {
        "database": "aethria_prod_snapshot",
        "migration_head": "20260814000006",
        "table_counts": {"startups": 225, "opportunities": 17},
        "startup_created_at": {
            "min": "2026-04-17T14:33:20.083714+00:00",
            "max": "2026-08-10T21:36:02.135987+00:00",
        },
        "startup_updated_at": {
            "min": "2026-04-17T14:35:11.532594+00:00",
            "max": "2026-08-11T13:06:12.699289+00:00",
        },
    }


def _facts():
    return {
        "database": "aethria_prod_snapshot",
        "migration_head": "20260814000006",
        "table_counts": {"startups": 225, "opportunities": 17},
        "startup_created_at": {
            "min": "2026-04-17T14:33:20.083714+00:00",
            "max": "2026-08-10T21:36:02.135987+00:00",
        },
        "startup_updated_at": {
            "min": "2026-04-17T14:35:11.532594+00:00",
            "max": "2026-08-11T13:06:12.699289+00:00",
        },
    }


def test_manifest_accepts_matching_snapshot_facts():
    assert validate_snapshot_facts(_facts(), _manifest()) == []


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("database", "aethria_test"),
        ("migration_head", "20260812000000"),
    ],
)
def test_manifest_rejects_identity_or_schema_drift(field, value):
    facts = _facts()
    facts[field] = value

    errors = validate_snapshot_facts(facts, _manifest())

    assert errors
    assert field in " ".join(errors)


def test_manifest_rejects_table_count_drift():
    facts = _facts()
    facts["table_counts"]["startups"] = 30

    errors = validate_snapshot_facts(facts, _manifest())

    assert errors == ["table_counts.startups expected 225, found 30"]
