"""Tests for truncation-safe JSON serialization + risk merging in partner prompts.

The partner LLM prompt previously char-sliced ``json.dumps(obj)[:n]``, which can
emit malformed JSON into the prompt. ``_json_within_budget`` must always return
VALID JSON while staying within budget when possible.
"""

import json

from partner.decision import _json_within_budget, _merge_risks


def test_small_object_is_returned_verbatim():
    obj = {"a": 1, "b": ["x", "y"]}
    out = _json_within_budget(obj, 1000)
    assert json.loads(out) == obj


def test_oversized_dict_stays_valid_json_and_within_budget():
    obj = {f"k{i}": "v" * 200 for i in range(50)}  # well over any small budget
    out = _json_within_budget(obj, 300)
    parsed = json.loads(out)  # must not raise
    assert isinstance(parsed, dict)
    assert len(out) <= 300
    assert parsed.get("_elided_keys") is True


def test_oversized_dict_drops_largest_values_first():
    obj = {"keep": "small", "huge": "x" * 5000}
    out = _json_within_budget(obj, 200)
    parsed = json.loads(out)
    assert "keep" in parsed  # small key survives
    assert "huge" not in parsed  # the giant value is dropped
    assert parsed.get("_elided_keys") is True


def test_oversized_list_stays_valid_json_and_marks_elision():
    obj = ["item-" + "y" * 100 for _ in range(40)]
    out = _json_within_budget(obj, 300)
    parsed = json.loads(out)  # must not raise
    assert isinstance(parsed, list)
    assert len(out) <= 300
    assert any("elided" in str(x) for x in parsed)


def test_nested_structured_scoring_shape_stays_valid_when_clipped():
    # Mirrors the structured_scoring blob passed into the partner prompt.
    obj = {
        dim: {"score": 6.0, "components": {f"c{i}": {"reasoning": "r" * 80} for i in range(5)}}
        for dim in ("market", "product", "technical", "execution", "defensibility")
    }
    out = _json_within_budget(obj, 400)
    json.loads(out)  # the key assertion: parses cleanly
    assert len(out) <= 400


def test_merge_risks_dedupes_preserves_order_and_caps():
    out = _merge_risks(["a", "b", "a"], ["b", "c", "d", "e", "f"])
    assert out == ["a", "b", "c", "d", "e"]  # order preserved, deduped, capped at 5


def test_merge_risks_handles_none():
    assert _merge_risks(None, None) == []
    assert _merge_risks(["a"], None) == ["a"]
