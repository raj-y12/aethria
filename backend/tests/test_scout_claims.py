from canonical_scout_claims import derive_scout_claims


def test_derives_only_decision_bearing_claims_with_matching_source_evidence():
    claims = derive_scout_claims(
        {
            "funding_stage": "Seed",
            "est_tam": "$2B",
            "traction_facts": {"revenue": "$4M ARR", "employees": "40"},
            "solution": "Workflow automation for finance teams",
            "source_evidence": [
                {"url": "https://acme.example/metrics", "snippet": "Acme reports $4M ARR in a $2B market."},
                {"url": "https://news.example/acme", "snippet": "Acme raised a Seed round to expand its workflow product."},
            ],
        }
    )

    assert {claim["claim_type"] for claim in claims} == {
        "traction_revenue",
        "revenue_amount",
        "market_size",
        "funding_stage",
        "product_capability",
    }
    assert all(claim["_supporting_indexes"] for claim in claims)


def test_does_not_promote_scout_prose_or_unmatched_fields_to_claims():
    claims = derive_scout_claims(
        {
            "funding_stage": "Seed",
            "est_tam": "$2B",
            "solution": "A revolutionary platform with huge market potential",
            "source_evidence": [
                {"url": "https://acme.example", "snippet": "Acme is a company."},
            ],
        }
    )

    assert claims == []


def test_claims_preserve_source_indexes_and_normalized_values():
    claims = derive_scout_claims(
        {
            "funding_stage": "Series A",
            "source_evidence": [
                {"url": "https://news.example/acme", "snippet": "The Series A funds product development."},
            ],
        }
    )

    assert claims[0]["claim_type"] == "funding_stage"
    assert claims[0]["normalized_value"] == {"stage": "Series A"}
    assert claims[0]["_supporting_indexes"] == [0]
