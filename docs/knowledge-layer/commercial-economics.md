# Canonical commercial and economic evidence

The commercial slice records only explicit source-grounded facts about how a
company makes money and what measurable economics are reported. It does not
canonicalize business-model quality or investment judgment.

Supported bounded claim families include payer type, revenue model, pricing,
revenue/ARR/GMV/bookings amounts, gross and contribution margin, unit economics,
customer concentration, retention/churn, and customer counts. Values retain
their original metric and textual amount; ARR, revenue, GMV, bookings, gross
margin, and contribution margin are never collapsed into one field. Periods are
retained when stated in the source.

Unknown dimensions remain explicit in the commercial ContextAssembler packet.
Conflicting claims remain separate and source-linked. Existing evidence
filtering preserves tenant boundaries, access class, freshness, verification,
and prompt-injection protections.

Reviewer receives this packet as factual context for `business_model_analysis`.
Statements such as “attractive economics”, “scalable model”, or “strong pricing
power” remain Reviewer judgments. The contradiction gate only protects direct
factual claims such as “no recurring revenue” when a verified recurring revenue
model is present.

Periodic and on-demand Reviewer paths both persist the guarded primary output;
post-review compatibility enrichment is therefore not allowed to feed an
unguarded Reviewer judgment back into Scout fields.

The slice adds no retrieval providers, database tables, or LLM calls. The
representative fixture produces one claim per explicitly evidenced commercial
fact and keeps the packet within the existing 4,000-character bound.
