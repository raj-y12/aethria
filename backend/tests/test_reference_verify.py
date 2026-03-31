"""Unit tests for reference verification (no network when probing is skipped)."""
import pytest

from scout.schema import validate_scout_output


def test_registrable_domain_and_parallel_detection():
    from utils.reference_verify import (
        is_parallel_same_slug_different_registrable,
        registrable_domain,
        reference_has_anchor_conflict,
    )

    assert registrable_domain("www.aethria.co") == "aethria.co"
    assert registrable_domain("aethria.com") == "aethria.com"
    assert is_parallel_same_slug_different_registrable("aethria.com", "aethria.co") is True
    assert is_parallel_same_slug_different_registrable("www.aethria.co", "aethria.co") is False
    assert is_parallel_same_slug_different_registrable("stripe.com", "plaid.com") is False
    assert reference_has_anchor_conflict("See https://aethria.com/about", "aethria.co") is True
    assert reference_has_anchor_conflict("See https://aethria.co/", "aethria.co") is False
    assert reference_has_anchor_conflict("TechCrunch https://techcrunch.com/x", "aethria.co") is False


def test_filter_anchor_conflicts():
    from utils.reference_verify import filter_references_anchor_conflicts

    refs = [
        "Us https://aethria.co/",
        "Wrong https://aethria.com/",
        "News https://techcrunch.com/foo",
    ]
    out = filter_references_anchor_conflicts(refs, "aethria.co")
    assert "aethria.co" in "".join(out)
    assert "aethria.com" not in "".join(out)
    assert any("techcrunch" in r for r in out)


def test_schema_requires_https_in_reference_line():
    base = {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "scout_type": "market_driven",
        "name": "ExampleCo",
        "one_line": "x",
        "sector": "x",
        "problem": "p",
        "solution": "s",
        "target_users": "t",
        "why_now": "w",
        "confidence": 0.7,
        "primary_thesis": "t",
        "key_assumptions": ["a", "b"],
        "biggest_unknown": "u",
        "references": ["Just Crunchbase article no url"],
    }
    with pytest.raises(ValueError, match="http"):
        validate_scout_output(dict(base))

    ok = dict(base)
    ok["references"] = ["ExampleCo — https://example.co/hello"]
    validate_scout_output(ok)


def test_finalize_skips_probe_when_env_set(monkeypatch):
    monkeypatch.setenv("SKIP_REFERENCE_URL_VERIFY", "1")
    from utils.reference_verify import finalize_scout_references

    output = {
        "references": [
            "Bad TLD https://aethria.com/",
            "OK https://aethria.co/",
        ]
    }
    finalize_scout_references(output, anchor_hostname="aethria.co")
    assert len(output["references"]) == 1
    assert "aethria.co" in output["references"][0]
