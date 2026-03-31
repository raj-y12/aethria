from partner.decision import PartnerDecisionEngine


def test_normalize_next_action_from_inline_numbered_text():
    engine = PartnerDecisionEngine(use_llm_fallback=False, api_key=None)
    raw = "1) Gather team bios 2) Validate TAM and pricing 3) Build milestone term sheet"

    normalized = engine._normalize_next_action(raw)

    assert normalized.startswith("1) Gather team bios")
    assert "\n2) Validate TAM and pricing" in normalized
    assert "\n3) Build milestone term sheet" in normalized


def test_normalize_next_action_keeps_single_paragraph_text():
    engine = PartnerDecisionEngine(use_llm_fallback=False, api_key=None)
    raw = "Schedule a single diligence deep-dive and return with findings."

    normalized = engine._normalize_next_action(raw)

    assert normalized == raw
