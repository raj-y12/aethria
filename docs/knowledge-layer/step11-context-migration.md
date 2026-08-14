# Step 11 — broader ContextAssembler migration

Step 11 extends the canonical context path without changing personas, scoring,
Partner policy, memo shape, CRM projection, Fund Intelligence, or frontend
contracts. Semantic retrieval, embeddings, pgvector, and RAG remain deferred.

## Audit classification

| Domain | Classification | Reason |
| --- | --- | --- |
| Regulatory | Canonical-ready | Existing regulatory claim/evidence packet and contradiction guard. |
| Founder | Canonical-ready | Canonical people claims with legacy fallback and uncertainty semantics. |
| Funding | Canonical-ready | `funding_stage` claims are source-linked and assembled through ContextAssembler. |
| Market | Canonical-ready for structured TAM/market-size facts | `market_size` claims are source-linked; narrative market prose remains compatibility input. |
| Traction | Canonical-ready for structured traction facts | `traction_revenue` claims are source-linked; unsupported fields remain legacy. |
| Product / technical | Partially canonical | `product_capability` exists, but the Scout solution narrative is still load-bearing and is not removed. |
| Competition | Legacy-only | No bounded canonical competition claim model with demonstrated parity. |
| Business model | Legacy-only | No bounded canonical business-model claim model with demonstrated parity. |

## Migration behavior

Reviewer receives canonical criterion packets whenever they contain supported
claims and eligible evidence. When canonical coverage is present, the equivalent
legacy Scout extras are suppressed for funding stage, estimated TAM, and
structured traction. Location, references, company description, solution, and
other fields remain available because they are not equivalent canonical packets
or are still needed for compatibility and grounding.

If coverage is absent or partial, the legacy fields remain in the prompt. The
ContextAssembler continues to enforce tenant checks, public/tenant-confidential
access filtering, freshness/expiry filtering, prompt-injection filtering,
supporting/contradicting evidence separation, bounded output, and explicit
missing-information semantics.

## Prompt reduction

The exact reduction is data-dependent and should be recorded from the Reviewer
prompt telemetry. The Step 11 regression fixture demonstrates a reduction of at
least 80 characters when funding, market, and traction packets are covered; the
canonical packets replace those redundant Scout extras while retaining bounded
source-linked context.
