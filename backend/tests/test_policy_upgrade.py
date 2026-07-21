from copy import deepcopy

import pytest


def _operator_config():
    return {
        "scoringWeights": [
            {"key": "market", "weight": "30.0"},
            {"key": "product", "weight": "25"},
            {"key": "technical", "weight": "20.0"},
            {"key": "execution", "weight": "15"},
            {"key": "defensibility", "weight": "10.0"},
        ],
        "thresholds": {
            "autoPass": "39",
            "monitor": "59.0",
            "escalation": "75",
            "partnerReview": "60.0",
        },
        "rubric": [],
    }


class _RpcResult:
    def __init__(self, apply):
        self._apply = apply

    def execute(self):
        return self._apply()


class _Client:
    def __init__(self, apply):
        self.apply = apply
        self.calls = []

    def rpc(self, name, params):
        self.calls.append((name, deepcopy(params)))
        return _RpcResult(lambda: self.apply(name, params))


def _wire_store(monkeypatch, *, fail_rpc=False):
    import services.scoring.policy_upgrade as upgrade

    settings = {
        "user-a": {
            "fund_config": {
                **_operator_config(),
                "activePolicyVersionId": "legacy-policy-a",
                "publishedPolicyHash": "legacy-hash-a",
            },
            "agent_config": {"reviewers_enabled": True},
        },
        "user-b": {
            "fund_config": {
                "activePolicyVersionId": "legacy-policy-b",
                "publishedPolicyHash": "legacy-hash-b",
            }
        },
    }
    versions = {
        "user-a": [
            {
                "id": "legacy-policy-a",
                "policy_version_id": "legacy-policy-a",
                "policy_hash": "legacy-hash-a",
                "dimensions": {},
            }
        ],
        "user-b": [
            {
                "id": "legacy-policy-b",
                "policy_version_id": "legacy-policy-b",
                "policy_hash": "legacy-hash-b",
                "dimensions": {},
            }
        ],
    }
    reads = []

    def load_settings(_table, key, *, user_id):
        reads.append(("settings", key, user_id))
        return deepcopy(settings[user_id])

    def load_versions(_table, *, user_id):
        reads.append(("versions", user_id))
        return deepcopy(versions[user_id])

    def apply(name, params):
        if fail_rpc:
            raise ConnectionError("rpc unavailable")
        assert name == "upgrade_fund_policy"
        uid = params["p_user_id"]
        current = settings[uid]["fund_config"]
        assert current["activePolicyVersionId"] == params["p_expected_policy_id"]
        assert current["publishedPolicyHash"] == params["p_expected_policy_hash"]
        versions[uid].append(deepcopy(params["p_policy_record"]))
        settings[uid] = deepcopy(params["p_settings_data"])
        return type("Response", (), {"data": {"status": "applied"}})()

    client = _Client(apply)
    monkeypatch.setattr(upgrade, "doc_get_strict", load_settings)
    monkeypatch.setattr(upgrade, "list_get_all_strict", load_versions)
    monkeypatch.setattr(upgrade, "get_service_client", lambda: client)
    return upgrade, settings, versions, reads, client


def test_legacy_upgrade_dry_run_reports_exact_transition_without_mutation(monkeypatch):
    upgrade, settings, versions, reads, client = _wire_store(monkeypatch)
    before_settings = deepcopy(settings)
    before_versions = deepcopy(versions)

    report = upgrade.upgrade_published_policy(
        "user-a", fund_config=_operator_config(), apply=False
    )

    assert report.mode.value == "dry_run"
    assert report.status.value == "upgrade_required"
    assert report.old_policy_state.value == "legacy"
    assert report.old_policy_id == "legacy-policy-a"
    assert report.old_policy_hash == "legacy-hash-a"
    assert report.new_policy_id.startswith("policy_upgrade_")
    assert report.new_policy_hash
    assert report.appended is False
    assert report.pointer_switched is False
    assert settings == before_settings
    assert versions == before_versions
    assert client.calls == []
    assert all("user-b" not in read for read in reads)


def test_legacy_upgrade_apply_is_atomic_normalized_and_idempotent(monkeypatch):
    upgrade, settings, versions, _reads, client = _wire_store(monkeypatch)

    applied = upgrade.upgrade_published_policy(
        "user-a", fund_config=_operator_config(), apply=True
    )
    rerun = upgrade.upgrade_published_policy(
        "user-a", fund_config=_operator_config(), apply=True
    )

    assert applied.status.value == "applied"
    assert applied.appended is True
    assert applied.pointer_switched is True
    assert len(client.calls) == 1
    record = versions["user-a"][-1]
    assert record["policy_version_id"] == applied.new_policy_id
    assert record["policy_hash"] == applied.new_policy_hash
    assert record["dimensions"]["market"]["weight"] == 30.0
    assert isinstance(record["dimensions"]["market"]["weight"], float)
    assert record["decision_inputs"]["thresholds"]["partnerReview"] == 60.0
    assert settings["user-a"]["fund_config"]["activePolicyVersionId"] == applied.new_policy_id
    assert settings["user-a"]["fund_config"]["publishedPolicyHash"] == applied.new_policy_hash
    assert rerun.status.value == "already_current"
    assert rerun.appended is False
    assert rerun.pointer_switched is False


def test_compile_failure_never_calls_rpc_or_moves_active_pointer(monkeypatch):
    upgrade, settings, versions, _reads, client = _wire_store(monkeypatch)
    before_settings = deepcopy(settings)
    before_versions = deepcopy(versions)
    invalid = _operator_config()
    invalid["rubric"] = [
        {
            "id": "bad",
            "dimension": "market",
            "weight": 0,
            "examples": {},
        }
    ]

    with pytest.raises(upgrade.PolicyValidationError):
        upgrade.upgrade_published_policy(
            "user-a", fund_config=invalid, apply=True
        )

    assert client.calls == []
    assert settings == before_settings
    assert versions == before_versions


def test_rpc_failure_cannot_move_pointer_or_append_version(monkeypatch):
    upgrade, settings, versions, _reads, _client = _wire_store(
        monkeypatch, fail_rpc=True
    )
    before_settings = deepcopy(settings)
    before_versions = deepcopy(versions)

    with pytest.raises(upgrade.PolicyUpgradeStoreUnavailable):
        upgrade.upgrade_published_policy(
            "user-a", fund_config=_operator_config(), apply=True
        )

    assert settings == before_settings
    assert versions == before_versions


def test_upgrade_is_tenant_scoped_and_cannot_touch_another_tenant(monkeypatch):
    upgrade, settings, versions, reads, client = _wire_store(monkeypatch)
    tenant_b_settings = deepcopy(settings["user-b"])
    tenant_b_versions = deepcopy(versions["user-b"])

    upgrade.upgrade_published_policy(
        "user-a", fund_config=_operator_config(), apply=True
    )

    assert settings["user-b"] == tenant_b_settings
    assert versions["user-b"] == tenant_b_versions
    assert client.calls[0][1]["p_user_id"] == "user-a"
    assert all("user-b" not in read for read in reads)


def test_complete_equivalent_policy_is_already_current_without_republishing(monkeypatch):
    import services.scoring.policy_upgrade as upgrade
    from services.scoring.policy_compiler import compile_policy_from_fund_config

    compiled = compile_policy_from_fund_config(
        _operator_config(), require_publish_ready=True
    )
    current_id = "existing-complete-policy"
    current = {
        **compiled,
        "id": current_id,
        "policy_version_id": current_id,
        "published_at": "2026-07-21T12:00:00+00:00",
    }
    settings = {
        "fund_config": {
            **_operator_config(),
            "activePolicyVersionId": current_id,
            "publishedPolicyHash": compiled["policy_hash"],
        }
    }
    monkeypatch.setattr(
        upgrade,
        "doc_get_strict",
        lambda *_args, **_kwargs: deepcopy(settings),
    )
    monkeypatch.setattr(
        upgrade,
        "list_get_all_strict",
        lambda *_args, **_kwargs: [deepcopy(current)],
    )
    monkeypatch.setattr(
        upgrade,
        "get_service_client",
        lambda: pytest.fail("already-current policy must not call the upgrade RPC"),
    )

    report = upgrade.upgrade_published_policy(
        "user-a", fund_config=_operator_config(), apply=True
    )

    assert report.status.value == "already_current"
    assert report.new_policy_id == current_id
    assert report.new_policy_hash == compiled["policy_hash"]
