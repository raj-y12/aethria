# Scout canonical claim bridge

Scout JSON remains the compatibility payload used by the existing Reviewer and
Partner paths. When a Scout payload also contains source snippets, the bounded
bridge in `backend/canonical_scout_claims.py` derives only four decision-bearing
claim families:

- `funding_stage`
- `market_size`
- `traction_revenue`
- `product_capability`

Each claim links to the source evidence item that matched its deterministic
pattern. Narrative fields are never promoted without matching source content.
URL-only citations therefore remain references, not evidence-backed claims.

The bridge reuses the existing evidence artifact, evidence item, claim, and
claim-evidence-link tables. It does not replace Scout JSON, migrate Reviewer
prompts, or introduce competition/business-model claims; those are currently
Reviewer outputs and remain outside this slice.
