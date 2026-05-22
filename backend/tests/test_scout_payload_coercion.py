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


def test_postprocess_fail_open_keeps_valid_non_allowlisted_references(monkeypatch):
    monkeypatch.setenv("SKIP_REFERENCE_URL_VERIFY", "1")
    scout = DummyScout(
        scout_type="market_driven",
        system_prompt="test",
        api_key="test-key",
        tenant_user_id="user_test_123",
    )
    payload = {
        "name": "Acme Robotics",
        "one_line": "Warehouse robotics automation",
        "sector": "Robotics",
        "problem": "Manual warehouse workflows are brittle.",
        "solution": "Acme automates picking and routing.",
        "target_users": "Warehouse operators",
        "why_now": "Labor shortages make automation urgent.",
        "confidence": 0.81,
        "primary_thesis": "Automation wedge into warehouse labor.",
        "key_assumptions": ["Demand persists", "Deployments stay economical"],
        "biggest_unknown": "Sales cycles with enterprise buyers.",
        "references": [
            "Acme Robotics official site - https://acmerobotics.com",
            "Acme Robotics team - https://www.linkedin.com/company/acme-robotics/",
        ],
    }
    out = scout._postprocess_scout_dict(
        payload,
        source_pack={
            "url_allowlist": {"https://acmerobotics.com"},
            "sources": [{"url": "https://acmerobotics.com", "title": "Official site", "snippet": ""}],
        },
        grounded_enabled=True,
        fail_closed=False,
        explicit_website="https://acmerobotics.com",
    )
    assert out is not None
    refs = "\n".join(out["references"])
    assert "acmerobotics.com" in refs
    assert "linkedin.com/company/acme-robotics" in refs


def test_postprocess_fail_closed_still_enforces_allowlist(monkeypatch):
    monkeypatch.setenv("SKIP_REFERENCE_URL_VERIFY", "1")
    scout = DummyScout(
        scout_type="market_driven",
        system_prompt="test",
        api_key="test-key",
        tenant_user_id="user_test_123",
    )
    payload = {
        "name": "Acme Robotics",
        "one_line": "Warehouse robotics automation",
        "sector": "Robotics",
        "problem": "Manual warehouse workflows are brittle.",
        "solution": "Acme automates picking and routing.",
        "target_users": "Warehouse operators",
        "why_now": "Labor shortages make automation urgent.",
        "confidence": 0.81,
        "primary_thesis": "Automation wedge into warehouse labor.",
        "key_assumptions": ["Demand persists", "Deployments stay economical"],
        "biggest_unknown": "Sales cycles with enterprise buyers.",
        "references": [
            "Acme Robotics team - https://www.linkedin.com/company/acme-robotics/",
        ],
    }
    out = scout._postprocess_scout_dict(
        payload,
        source_pack={
            "url_allowlist": {"https://acmerobotics.com"},
            "sources": [{"url": "https://acmerobotics.com", "title": "Official site", "snippet": ""}],
        },
        grounded_enabled=True,
        fail_closed=True,
        explicit_website=None,
    )
    assert out is None
