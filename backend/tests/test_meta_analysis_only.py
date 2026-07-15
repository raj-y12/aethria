from unittest.mock import MagicMock, patch

from meta.agent import MetaAgent


def _sufficient_signal():
    return {
        "data_sufficiency": {"total_reviews": 25, "total_decisions": 12},
        "pipeline_health": {},
        "scout_performance": {},
        "reviewer_health": {},
    }


def test_automatic_meta_cycle_reports_proposals_without_applying_them(monkeypatch):
    agent = MetaAgent(user_id="analysis-only-user")
    agent.min_reviews = 1
    agent.min_decisions = 1
    weight_proposals = [
        {
            "scout_type": "MarketDrivenScout",
            "previous_weight": 0.25,
            "new_weight": 0.3,
            "reasoning": "representative proposal",
            "applied_at": "2026-07-15T12:00:00+00:00",
            "cycle_number": 4,
        }
    ]
    calibration_proposals = [
        {
            "parameter": "confidence_threshold",
            "previous_value": 0.5,
            "new_value": 0.45,
            "direction": "loosened",
            "reasoning": "representative proposal",
            "triggered_by": "too strict",
            "applied_at": "2026-07-15T12:00:00+00:00",
            "cycle_number": 4,
        }
    ]
    prompt_proposals = [
        {
            "type": "prompt_proposal",
            "mutation_id": "proposal-1",
            "agent_target": "MarketDrivenScout",
            "promoted": False,
            "activation_status": "pending_operator_promotion",
        }
    ]

    monkeypatch.setattr(agent, "_increment_cycle", lambda: 4)

    with patch("meta.agent.MetaAnalyser") as analyser_cls, patch(
        "meta.agent.PromptMutator"
    ) as mutator_cls, patch("meta.agent.ScoutReweighter") as reweighter_cls, patch(
        "meta.agent.ThresholdCalibrator"
    ) as calibrator_cls, patch("meta.agent._append_to_json_list"):
        analyser_cls.return_value.analyse.return_value = _sufficient_signal()
        mutator_cls.return_value.decide.return_value = [{"agent_target": "x"}]
        mutator_cls.return_value.apply.return_value = prompt_proposals
        reweighter_cls.return_value.decide.return_value = weight_proposals
        calibrator_cls.return_value.decide.return_value = calibration_proposals

        report = agent._run_cycle_sync()

    reweighter_cls.return_value.apply.assert_not_called()
    calibrator_cls.return_value.apply.assert_not_called()
    assert report["analysis_only"] is True
    assert report["production_mutations_applied"] == 0
    assert report["prompt_proposals"] == prompt_proposals
    assert report["weight_proposals"] == weight_proposals
    assert report["calibration_proposals"] == calibration_proposals
    assert report["weight_updates"] == weight_proposals
    assert report["calibration_changes"] == calibration_proposals
    assert report["mutations_applied"] == []


def test_insufficient_data_meta_report_is_still_explicitly_analysis_only(monkeypatch):
    agent = MetaAgent(user_id="analysis-only-user")
    monkeypatch.setattr(agent, "_increment_cycle", lambda: 2)
    insufficient = {
        "data_sufficiency": {"total_reviews": 0, "total_decisions": 0}
    }

    with patch("meta.agent.MetaAnalyser") as analyser_cls, patch(
        "meta.agent._append_to_json_list"
    ):
        analyser_cls.return_value.analyse.return_value = insufficient
        report = agent._run_cycle_sync()

    assert report["analysis_only"] is True
    assert report["production_mutations_applied"] == 0
    assert report["weight_proposals"] == []
    assert report["calibration_proposals"] == []
    assert report["mutations_applied"] == []
