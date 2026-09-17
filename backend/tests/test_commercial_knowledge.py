from context import ContextAssembler, derive_commercial_claims, derive_scout_claims


def _claims(text):
    return derive_commercial_claims({
        "source_evidence": [{"url": "https://source.example/economics", "snippet": text}],
    })


def test_explicit_revenue_model_and_payer_are_canonical_facts():
    claims = _claims("The company charges enterprise logistics operators a 2% transaction fee on each booking.")
    by_type = {row["claim_type"]: row for row in claims}
    assert by_type["payer_type"]["normalized_value"]["payer"] == "enterprise logistics operators"
    assert by_type["revenue_model"]["normalized_value"]["model"] == "transaction_fee"
    assert by_type["pricing"]["normalized_value"]["value"] == "2% transaction fee"
    assert all(row["_supporting_indexes"] == [0] for row in claims)


def test_revenue_units_are_distinguished_and_not_collapsed():
    claims = _claims("The company reports €10m ARR, €4m revenue, and €30m GMV for 2025.")
    values = {(row["claim_type"], row["normalized_value"].get("metric")) for row in claims}
    assert ("revenue_amount", "arr") in values
    assert ("revenue_amount", "revenue") in values
    assert ("revenue_amount", "gmv") in values
    assert all(row["normalized_value"].get("period") == "2025" for row in claims if row["claim_type"] == "revenue_amount")


def test_explicit_margins_unit_economics_and_retention_are_preserved():
    claims = _claims("Gross margin is 72%; CAC is €100 and LTV is €900. Net revenue retention is 118%.")
    assert {row["claim_type"] for row in claims} == {"gross_margin", "unit_economics", "retention_churn"}
    assert any(row["normalized_value"].get("metric") == "gross_margin" for row in claims)
    assert any(row["normalized_value"].get("metric") == "cac" for row in claims)
    assert any(row["normalized_value"].get("metric") == "net_revenue_retention" for row in claims)


def test_generic_economic_judgment_and_missing_data_are_not_claims():
    claims = _claims("The business model is strong, scalable, and capital efficient.")
    assert claims == []


def test_customer_concentration_and_conflicting_source_indexes_remain_source_grounded():
    claims = derive_commercial_claims({
        "source_evidence": [
            {"url": "https://one.example", "snippet": "The top customer represents 40% of revenue."},
            {"url": "https://two.example", "snippet": "The top customer represents 25% of revenue."},
        ]
    })
    concentration = [row for row in claims if row["claim_type"] == "customer_concentration"]
    assert len(concentration) == 2
    assert {row["normalized_value"]["percentage"] for row in concentration} == {"40%", "25%"}
    assert {tuple(row["_supporting_indexes"]) for row in concentration} == {(0,), (1,)}


def test_scout_bridge_and_context_assembler_carry_commercial_facts():
    scout = {"source_evidence": [{"url": "https://source.example", "snippet": "Customers pay a monthly subscription."}]}
    claims = derive_scout_claims(scout)
    commercial = [row for row in claims if row["claim_type"] == "revenue_model"]
    assert commercial and commercial[0]["normalized_value"]["model"] == "subscription"
    packet = ContextAssembler().assemble(
        user_id="fund-a",
        criterion="commercial",
        claims=[{"user_id": "fund-a", "claim_id": "c1", **commercial[0], "status": "current"}],
        evidence=[{"user_id": "fund-a", "claim_id": "c1", "relationship": "supports", "display_excerpt": commercial[0]["display_text"], "source_locator": "https://source.example", "access_class": "public"}],
    )
    assert packet["has_canonical_coverage"] is True
