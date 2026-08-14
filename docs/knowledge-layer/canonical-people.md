# Canonical people layer

Step 9 adds a tenant-scoped people projection for founder and cofounder identity.
`people` and `person_identifiers` structure identity; `company_people` preserves
company relationships; and `person_history` preserves bounded, temporal prior
employment and education history.

The evidence and claim ledger remains authoritative. New founder writes project
only grounded resolver output into these tables and link the resulting claims to
source evidence. Conflicting fields remain explicit, and shallow or ambiguous
identities stay unresolved. A verified external identifier is preferred for
deduplication; a name is never merged globally without company context.

The existing `scout_info.founder_resolution` shape remains intact as a migration
fallback. The existing founder ContextAssembler packet consumes canonical
`founder_*` claims when they are present and otherwise continues to use the
legacy resolution, preserving access filtering, provenance, boundedness, and
uncertainty semantics.
