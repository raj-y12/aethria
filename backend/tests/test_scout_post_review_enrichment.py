"""Post-review ScoutInfo enrichment."""

from models import ScoutInfo
from context import (
    infer_funding_stage_from_text,
    infer_funding_stage_from_review_text_enabled,
    merge_scout_info_enrichment,
)


def _minimal_scout(**kwargs) -> ScoutInfo:
    base = dict(
        startup_id="s1",
        name="Acme",
        one_line="AI",
        sector="Software",
        problem="p",
        solution="s",
        target_users="u",
        why_now="w",
        scout_type="market_driven",
        confidence_score=0.8,
        references=["https://acme.com/about"],
    )
    base.update(kwargs)
    return ScoutInfo(**base)


def test_infer_funding_disabled_by_default(monkeypatch):
    monkeypatch.delenv("SCOUT_ENRICH_INFER_FUNDING_STAGE", raising=False)
    assert infer_funding_stage_from_review_text_enabled() is False


def test_merge_fills_tam_from_raw_signals(monkeypatch):
    monkeypatch.setenv("SCOUT_POST_REVIEW_ENRICHMENT", "1")
    si = _minimal_scout(est_tam=None)
    review = {
        "structured_scoring": {
            "raw_signals": {
                "market": {
                    "tam": {"value": "$12B SAM", "confidence": 0.72},
                },
            },
        },
    }
    out = merge_scout_info_enrichment(si, review_output=review)
    assert out.est_tam == "$12B SAM"
    assert (out.field_provenance or {}).get("est_tam") == "reviewer_extraction"


def test_merge_skips_tam_when_scout_has_value(monkeypatch):
    monkeypatch.setenv("SCOUT_POST_REVIEW_ENRICHMENT", "1")
    si = _minimal_scout(est_tam="$1B")
    review = {
        "structured_scoring": {
            "raw_signals": {"market": {"tam": {"value": "$99B", "confidence": 0.9}}},
        },
    }
    out = merge_scout_info_enrichment(si, review_output=review)
    assert out.est_tam == "$1B"


def test_merge_funding_from_summary_when_infer_enabled(monkeypatch):
    monkeypatch.setenv("SCOUT_POST_REVIEW_ENRICHMENT", "1")
    monkeypatch.setenv("SCOUT_ENRICH_INFER_FUNDING_STAGE", "1")
    si = _minimal_scout(funding_stage="Unknown")
    review = {"overall_summary": "Acme raised a Series A led by Example Capital in 2024."}
    out = merge_scout_info_enrichment(si, review_output=review)
    assert out.funding_stage == "Series A"
    assert (out.field_provenance or {}).get("funding_stage") == "reviewer_text_inference"


def test_merge_funding_not_inferred_when_infer_disabled(monkeypatch):
    monkeypatch.setenv("SCOUT_POST_REVIEW_ENRICHMENT", "1")
    monkeypatch.delenv("SCOUT_ENRICH_INFER_FUNDING_STAGE", raising=False)
    si = _minimal_scout(funding_stage="Unknown")
    review = {"overall_summary": "Acme raised a Series A led by Example Capital in 2024."}
    out = merge_scout_info_enrichment(si, review_output=review)
    assert out.funding_stage == "Unknown"


def test_merge_appends_gap_urls(monkeypatch):
    monkeypatch.setenv("SCOUT_POST_REVIEW_ENRICHMENT", "1")
    si = _minimal_scout()
    review = {"overall_summary": "ok"}
    out = merge_scout_info_enrichment(
        si,
        review_output=review,
        gap_reference_urls=["https://techcrunch.com/acme"],
    )
    assert any("techcrunch.com" in r for r in (out.references or []))
    assert (out.field_provenance or {}).get("references") == "gap_retrieval"


def test_infer_funding_series_order():
    assert infer_funding_stage_from_text("Company completed Series B after Seed.") == "Series B"


def test_disabled_noop(monkeypatch):
    monkeypatch.setenv("SCOUT_POST_REVIEW_ENRICHMENT", "0")
    si = _minimal_scout(est_tam=None)
    review = {
        "structured_scoring": {
            "raw_signals": {"market": {"tam": {"value": "$2B", "confidence": 0.9}}},
        },
    }
    out = merge_scout_info_enrichment(si, review_output=review)
    assert out.est_tam is None
