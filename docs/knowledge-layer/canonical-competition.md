# Canonical competition evidence

The competition slice promotes only explicit source language into the existing
claim and evidence ledger. Supported forms include `competes with`,
`competitors include`, and `alternatives include`. The bounded claim families
are:

- `competitor_existence`
- `competitor_product_overlap`
- `competitor_segment_overlap`
- `competitor_geography_overlap`

Each claim retains its source excerpt and supporting evidence link. A competitor
name without a verified canonical company identity remains an unresolved name
in the claim value; it is not merged into a company by name alone. The
`company_competitors` table is the minimal tenant-scoped relationship structure
for future identity-resolved relationships and is linked to the authoritative
company and claim rows.

The ContextAssembler filters inactive, expired, restricted, and prompt-injection
evidence. It retains supporting and contradicting links and emits explicit
unknown fields when coverage is incomplete. Missing competitor evidence never
means no competition.

Reviewer receives the competition packet whenever it has canonical coverage and
otherwise retains the existing legacy path. The contradiction gate only guards
categorical claims such as “no credible competition” when verified competitor
evidence exists. It does not turn the existence of competitors into a
deterministic “crowded market” or “weak moat” conclusion.

## Bounded measurement fixture

For a source stating that a target competes with two named companies in an
explicit segment and geography, the fixture produces 2 competitor identities
and 8 claims (existence and product overlap for each, plus segment and
geography overlap for each). One source artifact and one evidence item are
ingested per source. Context output remains bounded at the existing 4,000
character default. No additional LLM calls or retrieval providers are used.
