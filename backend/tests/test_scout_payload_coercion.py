from scout.base import Scout


class DummyScout(Scout):
    pass


def test_coerce_payload_fixes_missing_name_and_target_users():
    scout = DummyScout(
        scout_type="market_driven",
        system_prompt="test",
        api_key="test-key",
        tenant_user_id="user_test_123",
    )
    payload = {
        "one_line": "Workflow AI for industrial inspections",
        "target_users": ["ops leaders", "field technicians"],
        "confidence": "0.84",
        "key_assumptions": "Users adopt quickly",
        "references": "Example - https://example.com",
    }
    out = scout._coerce_scout_payload(payload)
    assert isinstance(out["name"], str)
    assert out["name"] != ""
    assert isinstance(out["target_users"], str)
    assert "ops leaders" in out["target_users"]
    assert isinstance(out["confidence"], float)
    assert len(out["key_assumptions"]) >= 2
    assert isinstance(out["references"], list)

