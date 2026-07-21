import json
import sys

from services.scoring.policy_upgrade import (
    ExistingPolicyState,
    PolicyUpgradeMode,
    PolicyUpgradeStatus,
    PublishedPolicyUpgradeReport,
)


def test_policy_upgrade_cli_requires_explicit_mode_and_selected_config(
    monkeypatch, tmp_path, capsys
):
    from scripts import upgrade_published_policy as cli

    config = tmp_path / "fund-config.json"
    config.write_text(json.dumps({"fund_config": {"rubric": []}}))
    calls = []

    def upgrade(user_id, *, fund_config, apply):
        calls.append((user_id, fund_config, apply))
        return PublishedPolicyUpgradeReport(
            user_id=user_id,
            mode=PolicyUpgradeMode.APPLY if apply else PolicyUpgradeMode.DRY_RUN,
            status=(
                PolicyUpgradeStatus.APPLIED
                if apply
                else PolicyUpgradeStatus.UPGRADE_REQUIRED
            ),
            old_policy_state=ExistingPolicyState.LEGACY,
            old_policy_id="legacy-1",
            old_policy_hash="legacy-hash",
            new_policy_id="policy_upgrade_newhash",
            new_policy_hash="newhash",
            appended=apply,
            pointer_switched=apply,
        )

    monkeypatch.setattr(cli, "upgrade_published_policy", upgrade)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "upgrade_published_policy.py",
            "--user-id",
            "user-a",
            "--fund-config-file",
            str(config),
            "--dry-run",
            "--json",
        ],
    )

    assert cli.main() == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["mode"] == "dry_run"
    assert payload["status"] == "upgrade_required"
    assert calls == [("user-a", {"rubric": []}, False)]


def test_policy_upgrade_cli_apply_is_explicit(monkeypatch, tmp_path, capsys):
    from scripts import upgrade_published_policy as cli

    config = tmp_path / "fund-config.json"
    config.write_text(json.dumps({"rubric": []}))
    applied = []

    def upgrade(user_id, *, fund_config, apply):
        applied.append(apply)
        return PublishedPolicyUpgradeReport(
            user_id=user_id,
            mode=PolicyUpgradeMode.APPLY,
            status=PolicyUpgradeStatus.APPLIED,
            old_policy_state=ExistingPolicyState.MISSING,
            new_policy_id="policy_upgrade_newhash",
            new_policy_hash="newhash",
            appended=True,
            pointer_switched=True,
        )

    monkeypatch.setattr(cli, "upgrade_published_policy", upgrade)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "upgrade_published_policy.py",
            "--user-id",
            "user-a",
            "--fund-config-file",
            str(config),
            "--apply",
            "--json",
        ],
    )

    assert cli.main() == 0
    assert json.loads(capsys.readouterr().out)["status"] == "applied"
    assert applied == [True]
