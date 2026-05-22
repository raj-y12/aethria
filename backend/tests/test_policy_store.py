from services.scoring.policy_store import publish_policy


def _valid_fund_config():
    return {
        "rubric": [
            {
                "id": "market_conviction",
                "dimension": "market",
                "name": "Market conviction",
                "weight": 100,
                "examples": {
                    "score3": "Weak",
                    "score5": "Neutral",
                    "score7": "Good",
                    "score9": "Great",
                },
            }
        ]
    }


def test_publish_policy_deduplicates_same_hash(monkeypatch):
    import services.scoring.policy_store as store_mod

    settings = {"fund_config": _valid_fund_config()}
    versions = []
    saved = []

    monkeypatch.setattr(store_mod, "load_settings", lambda user_id, use_cache=True: dict(settings))
    monkeypatch.setattr(store_mod, "list_get_all", lambda table, user_id: list(versions))

    def fake_append(table, record, id_field="id", user_id=""):
        versions.append(dict(record))
        return record["id"]

    def fake_save(next_settings, user_id):
        saved.append(next_settings)
        settings.clear()
        settings.update(next_settings)

    monkeypatch.setattr(store_mod, "list_append", fake_append)
    monkeypatch.setattr(store_mod, "save_settings", fake_save)

    first = publish_policy("user_1")
    second = publish_policy("user_1")

    assert first["policy_hash"] == second["policy_hash"]
    assert len(versions) == 1
    assert saved[-1]["fund_config"]["activePolicyVersionId"] == first["policy_version_id"]
