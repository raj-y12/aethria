"""Founder enrichment: reuse of the reviewer gap pack and persistence onto ScoutInfo."""
from typing import Any, Dict, List

import pytest

from models import ScoutInfo
from resolver.founder_resolver import FounderCandidate, FounderResolution
from utils.founder_enrichment import (
    FOUNDER_PROVENANCE,
    accepted_founder_names,
    apply_founder_resolution_to_payload,
    founder_resolution_for_review,
    founder_resolution_from_gap_pack,
    is_founder_resolution_enabled,
    merge_founder_resolution_into_scout_info,
)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for key in (
        "FOUNDER_RESOLUTION_ENABLED",
        "FOUNDER_RESOLUTION_MIN_CONFIDENCE",
        "FOUNDER_RESOLUTION_MAX_NAMES",
        "REVIEWER_FOUNDER_FALLBACK_RETRIEVAL",
    ):
        monkeypatch.delenv(key, raising=False)


def _scout_info(**kwargs) -> ScoutInfo:
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


def _resolution(names_with_conf: List[tuple], **kwargs) -> FounderResolution:
    return FounderResolution(
        company="Acme",
        founders=[
            FounderCandidate(name=n, confidence=c, role="Founder") for n, c in names_with_conf
        ],
        resolution_status="FOUND",
        **kwargs,
    )


_TEAM_SOURCE = {
    "source_id": "S1",
    "title": "Acme — Team",
    "url": "https://acme.com/team",
    "snippet": "Ada Byron, Co-founder & CEO, previously worked at Stripe.",
}


# --------------------------------------------------------------------------- #
# Toggles and thresholds
# --------------------------------------------------------------------------- #


def test_enabled_by_default():
    assert is_founder_resolution_enabled() is True


def test_can_be_disabled(monkeypatch):
    monkeypatch.setenv("FOUNDER_RESOLUTION_ENABLED", "false")
    assert is_founder_resolution_enabled() is False


def test_low_confidence_candidates_are_not_promoted(monkeypatch):
    monkeypatch.setenv("FOUNDER_RESOLUTION_MIN_CONFIDENCE", "0.5")
    resolution = _resolution([("Ada Byron", 0.9), ("Noisy Match", 0.2)])
    assert accepted_founder_names(resolution) == ["Ada Byron"]


def test_promoted_names_are_capped(monkeypatch):
    monkeypatch.setenv("FOUNDER_RESOLUTION_MAX_NAMES", "2")
    resolution = _resolution([("A One", 0.9), ("B Two", 0.8), ("C Three", 0.7)])
    assert accepted_founder_names(resolution) == ["A One", "B Two"]


def test_name_cap_never_exceeds_the_scout_info_limit(monkeypatch):
    monkeypatch.setenv("FOUNDER_RESOLUTION_MAX_NAMES", "50")
    resolution = _resolution([(f"Person {i}", 0.9) for i in range(12)])
    names = accepted_founder_names(resolution)
    assert len(names) == 8
    # ScoutInfo rejects more than 8 names, so the cap must hold at the model too.
    _scout_info(founder_names=names)


# --------------------------------------------------------------------------- #
# Payload application (lookup stage)
# --------------------------------------------------------------------------- #


def test_payload_gets_structured_resolution_and_names():
    payload = apply_founder_resolution_to_payload(
        {"name": "Acme"}, _resolution([("Ada Byron", 0.8)])
    )
    assert payload["founder_names"] == ["Ada Byron"]
    assert payload["founder_resolution"]["founders"][0]["name"] == "Ada Byron"
    assert payload["field_provenance"]["founder_names"] == FOUNDER_PROVENANCE


def test_payload_names_are_never_overwritten():
    payload = apply_founder_resolution_to_payload(
        {"name": "Acme", "founder_names": ["Grace Hopper"]},
        _resolution([("Ada Byron", 0.9)]),
    )
    assert payload["founder_names"] == ["Grace Hopper"]
    # The structured resolution is still attached for auditability.
    assert payload["founder_resolution"]["founders"][0]["name"] == "Ada Byron"
    assert "founder_names" not in (payload.get("field_provenance") or {})


def test_payload_is_unchanged_without_a_resolution():
    original = {"name": "Acme"}
    assert apply_founder_resolution_to_payload(original, None) == original


def test_structured_resolution_is_attached_even_when_no_name_clears_the_floor(monkeypatch):
    monkeypatch.setenv("FOUNDER_RESOLUTION_MIN_CONFIDENCE", "0.9")
    payload = apply_founder_resolution_to_payload(
        {"name": "Acme"}, _resolution([("Ada Byron", 0.3)])
    )
    assert "founder_names" not in payload
    assert payload["founder_resolution"]["founders"][0]["name"] == "Ada Byron"


# --------------------------------------------------------------------------- #
# ScoutInfo persistence (reviewer stage)
# --------------------------------------------------------------------------- #


def test_scout_info_gains_founders_and_provenance():
    merged = merge_founder_resolution_into_scout_info(
        _scout_info(), _resolution([("Ada Byron", 0.8)])
    )
    assert merged.founder_names == ["Ada Byron"]
    assert merged.field_provenance["founder_names"] == FOUNDER_PROVENANCE
    assert merged.founder_resolution["resolution_status"] == "FOUND"


def test_scout_info_founders_are_never_overwritten():
    merged = merge_founder_resolution_into_scout_info(
        _scout_info(founder_names=["Grace Hopper"]), _resolution([("Ada Byron", 0.9)])
    )
    assert merged.founder_names == ["Grace Hopper"]
    assert merged.founder_resolution is not None


def test_existing_provenance_is_preserved():
    merged = merge_founder_resolution_into_scout_info(
        _scout_info(field_provenance={"est_tam": "reviewer_extraction"}),
        _resolution([("Ada Byron", 0.8)]),
    )
    assert merged.field_provenance["est_tam"] == "reviewer_extraction"
    assert merged.field_provenance["founder_names"] == FOUNDER_PROVENANCE


def test_scout_info_is_unchanged_without_a_resolution():
    original = _scout_info()
    assert merge_founder_resolution_into_scout_info(original, None) is original


# --------------------------------------------------------------------------- #
# Gap-pack reuse
# --------------------------------------------------------------------------- #


def test_gap_pack_is_reused_without_any_extra_retrieval(monkeypatch):
    def explode(*args, **kwargs):
        raise AssertionError("gap-pack reuse must not trigger new retrieval")

    monkeypatch.setattr("resolver.founder_resolver.resolve_founders", explode)
    resolution = founder_resolution_from_gap_pack(
        {"name": "Acme"},
        user_id="u1",
        pack={"provider": "exa", "sources": [_TEAM_SOURCE]},
    )
    assert resolution.founder_names() == ["Ada Byron"]
    assert resolution.founders[0].previous_employment == ["Stripe"]
    assert resolution.stage_log[0].stage == "reviewer_gap_pack"
    assert resolution.retrieval_provider == "exa"


def test_gap_pack_classifies_source_type_so_official_site_bonus_can_fire(monkeypatch):
    """Regression (audit HIGH-A3): this path used to leave every evidence
    item's source_type at its "other" default, so the official-site/
    crunchbase/news confidence bonuses in _candidate_confidence could never
    apply even when the reused evidence genuinely was the company's own team
    page -- silently under-scoring real founders for missing plumbing, not
    weak evidence."""
    monkeypatch.setattr(
        "resolver.founder_resolver.resolve_founders",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not retrieve")),
    )
    linkedin_source = {
        "source_id": "S2",
        "title": "Ada Byron - LinkedIn",
        "url": "https://linkedin.com/in/adabyron",
        "snippet": "Ada Byron, Co-founder & CEO of Acme.",
    }
    resolution = founder_resolution_from_gap_pack(
        {"name": "Acme", "lookup_website": "acme.com"},
        user_id="u1",
        pack={"provider": "exa", "sources": [_TEAM_SOURCE, linkedin_source]},
    )
    source_types = {e.url: e.source_type for e in resolution.founders[0].evidence}
    assert source_types["https://acme.com/team"] == "official_site"
    assert source_types["https://linkedin.com/in/adabyron"] == "linkedin"


def test_gap_pack_without_founders_can_fall_back_to_retrieval():
    calls: Dict[str, Any] = {}

    def fake_resolve(company, **kwargs):
        calls["company"] = company
        return _resolution([("Ada Byron", 0.7)])

    import resolver.founder_resolver as fr

    original = fr.resolve_founders
    fr.resolve_founders = fake_resolve
    try:
        resolution = founder_resolution_from_gap_pack(
            {"name": "Acme"},
            user_id="u1",
            pack={"sources": [{"title": "x", "url": "https://acme.com", "snippet": "no people"}]},
            allow_fallback_retrieval=True,
        )
    finally:
        fr.resolve_founders = original
    assert calls["company"] == "Acme"
    assert resolution.founder_names() == ["Ada Byron"]


def test_gap_pack_without_founders_returns_none_when_fallback_is_off():
    resolution = founder_resolution_from_gap_pack(
        {"name": "Acme"},
        user_id="u1",
        pack={"sources": [{"title": "x", "url": "https://acme.com", "snippet": "no people"}]},
        allow_fallback_retrieval=False,
    )
    assert resolution is None


# --------------------------------------------------------------------------- #
# Reviewer entry point
# --------------------------------------------------------------------------- #


def test_review_resolves_founders_from_the_retained_gap_sources():
    resolution = founder_resolution_for_review(
        {"name": "Acme"},
        {"_reviewer_gap_sources": [_TEAM_SOURCE], "_reviewer_gap_provider": "exa"},
        "u1",
    )
    assert resolution.founder_names() == ["Ada Byron"]


def test_review_skips_when_founders_are_already_known():
    assert (
        founder_resolution_for_review(
            {"name": "Acme", "founder_names": ["Grace Hopper"]},
            {"_reviewer_gap_sources": [_TEAM_SOURCE]},
            "u1",
        )
        is None
    )


def test_review_skips_when_no_gap_pack_was_retained():
    assert founder_resolution_for_review({"name": "Acme"}, {}, "u1") is None


def test_review_skips_when_disabled(monkeypatch):
    monkeypatch.setenv("FOUNDER_RESOLUTION_ENABLED", "false")
    assert (
        founder_resolution_for_review(
            {"name": "Acme"}, {"_reviewer_gap_sources": [_TEAM_SOURCE]}, "u1"
        )
        is None
    )


def test_review_adds_no_retrieval_by_default(monkeypatch):
    """The reviewer path already blocks on retrieval; reuse must not add more."""

    def explode(*args, **kwargs):
        raise AssertionError("reviewer-side founder resolution must not search by default")

    monkeypatch.setattr("resolver.founder_resolver.resolve_founders", explode)
    assert (
        founder_resolution_for_review(
            {"name": "Acme"},
            {"_reviewer_gap_sources": [{"title": "x", "url": "https://a.com", "snippet": "none"}]},
            "u1",
        )
        is None
    )


def test_review_failure_is_swallowed(monkeypatch):
    monkeypatch.setattr(
        "utils.founder_enrichment.founder_resolution_from_gap_pack",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    assert (
        founder_resolution_for_review(
            {"name": "Acme"}, {"_reviewer_gap_sources": [_TEAM_SOURCE]}, "u1"
        )
        is None
    )


# --------------------------------------------------------------------------- #
# Reviewer gap retrieval retains its pack
# --------------------------------------------------------------------------- #


def test_gap_retrieval_retains_sources_for_reuse(monkeypatch):
    from reviewer import gap_retrieval as reviewer_gap_retrieval

    monkeypatch.setattr(
        reviewer_gap_retrieval,
        "fetch_reviewer_gap_pack",
        lambda scout, user_id: {
            "provider": "exa",
            "sources": [_TEAM_SOURCE],
            "url_allowlist": {_TEAM_SOURCE["url"]},
        },
    )
    out = reviewer_gap_retrieval.enrich_scout_for_reviewer_llm({"name": "Acme"}, "u1")
    # Previously only the rendered prompt block and URLs survived.
    assert out["_reviewer_gap_sources"] == [_TEAM_SOURCE]
    assert out["_reviewer_gap_provider"] == "exa"
    assert out["_reviewer_web_supplement"]
    assert out["_reviewer_gap_reference_urls"] == [_TEAM_SOURCE["url"]]


def test_storage_persists_founder_resolution_through_add_review():
    """add_review must route founder resolution onto the stored ScoutInfo."""
    from utils.storage import Storage
    import tempfile, os

    with tempfile.TemporaryDirectory() as tmp:
        storage = Storage(file_path=os.path.join(tmp, "d.json"))
        scout_info = _scout_info(startup_id="s-1")
        storage.add_startup(scout_info)

        from models import ReviewInfo

        review = ReviewInfo(
            reviewer_agent_id="r1",
            market_score=7,
            product_score=7,
            technical_score=7,
            execution_score=7,
            overall_summary="ok",
            key_risks=["r"],
            verdict="STRONG",
        )
        assert storage.add_review(
            "s-1",
            review,
            enrichment_founder_resolution=_resolution([("Ada Byron", 0.8)]),
        )
        stored = storage.get_startup("s-1")
        assert stored.scout_info.founder_names == ["Ada Byron"]
        assert stored.scout_info.field_provenance["founder_names"] == FOUNDER_PROVENANCE
        assert stored.scout_info.founder_resolution["company"] == "Acme"
