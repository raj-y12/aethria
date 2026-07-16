"""Meta Agent Phase 1: prompt validation and gated apply."""
from unittest.mock import MagicMock, patch

from meta.mutator import PromptMutator, validate_mutated_prompt


def test_validate_empty_rejected():
    assert validate_mutated_prompt("", "current", max_chars=1000, max_lines=100, min_ratio=0.85, max_growth=3.0) == "empty_prompt"
    assert validate_mutated_prompt("   ", "current", max_chars=1000, max_lines=100, min_ratio=0.85, max_growth=3.0) == "empty_prompt"


def test_validate_max_chars():
    cur = "a" * 100
    new = "b" * 50
    assert validate_mutated_prompt(new, cur, max_chars=40, max_lines=500, min_ratio=0.5, max_growth=10.0) == "exceeds_max_chars:50>40"


def test_validate_max_lines():
    cur = "a"
    new = "x\n" * 15  # 15 newlines -> 16 lines
    assert (
        validate_mutated_prompt(new, cur, max_chars=10000, max_lines=10, min_ratio=0.1, max_growth=100.0)
        == "exceeds_max_lines:16>10"
    )


def test_validate_min_ratio():
    cur = "a" * 100
    new = "b" * 50
    err = validate_mutated_prompt(new, cur, max_chars=10000, max_lines=500, min_ratio=0.85, max_growth=10.0)
    assert err and err.startswith("shorter_than_min_ratio")


def test_validate_max_growth():
    cur = "a" * 100
    new = "b" * 400
    err = validate_mutated_prompt(new, cur, max_chars=10000, max_lines=500, min_ratio=0.5, max_growth=2.0)
    assert err and err.startswith("longer_than_max_growth")


def test_validate_ok():
    cur = "a" * 200
    new = "b" * 200
    assert validate_mutated_prompt(new, cur, max_chars=10000, max_lines=500, min_ratio=0.85, max_growth=3.0) is None


def test_mutator_apply_one_skips_set_prompt_without_auto_apply(monkeypatch):
    monkeypatch.delenv("META_AGENT_PROMPT_AUTO_APPLY", raising=False)
    signal = {"pipeline_health": {}}
    mutator = PromptMutator(signal, cycle_number=7, user_id="test-user-meta")
    mock_scout = MagicMock()
    mock_scout.scout_type = "market_driven"
    mock_scout.system_prompt = "scout baseline " * 40
    mock_engine = MagicMock()
    mock_engine.scouts = [mock_scout]
    target = {
        "agent_target": "MarketDrivenScout",
        "mutation_type": "scout_prompt",
        "trigger": "test",
        "signal": {"acceptance_rate": 0.1},
    }
    new_prompt = "mutated scout text " * 40

    with patch.object(mutator, "_call_llm", return_value=(new_prompt, "test reasoning")):
        with patch.object(mutator, "_set_agent_prompt") as set_prompt:
            with patch("meta.mutator._append_to_json_list"):
                with patch("meta.mutator._read_json_dict", return_value={}):
                    with patch("meta.mutator._atomic_write"):
                        out = mutator._apply_one(target, mock_engine, None)
    assert out is not None
    assert out.get("type") == "prompt_proposal"
    assert out.get("promoted") is False
    assert out.get("activation_status") == "pending_operator_promotion"
    set_prompt.assert_not_called()


def test_mutator_apply_one_ignores_auto_apply_environment_switch(monkeypatch):
    monkeypatch.setenv("META_AGENT_PROMPT_AUTO_APPLY", "true")
    signal = {"pipeline_health": {}}
    with patch(
        "utils.settings_loader.load_settings",
        return_value={"workspace": {"meta_prompt_auto_apply": True}},
    ):
        mutator = PromptMutator(signal, cycle_number=8, user_id="test-user-meta-2")
    mock_scout = MagicMock()
    mock_scout.scout_type = "market_driven"
    mock_scout.system_prompt = "scout baseline " * 40
    mock_engine = MagicMock()
    mock_engine.scouts = [mock_scout]
    target = {
        "agent_target": "MarketDrivenScout",
        "mutation_type": "scout_prompt",
        "trigger": "test",
        "signal": {},
    }
    new_prompt = "mutated scout text " * 40

    with patch.object(mutator, "_call_llm", return_value=(new_prompt, "r")):
        with patch.object(mutator, "_set_agent_prompt") as set_prompt:
            with patch("meta.mutator._append_to_json_list"):
                with patch("meta.mutator._read_json_dict", return_value={}):
                    with patch("meta.mutator._atomic_write"):
                        out = mutator._apply_one(target, mock_engine, None)
    assert out is not None
    assert out["activation_status"] == "pending_operator_promotion"
    set_prompt.assert_not_called()
