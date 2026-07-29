# ADR-0009 — Rule-based partner decisions; the LLM only for declared edge cases

**Status:** Accepted

## Context

The partner stage issues INVEST / PASS / MONITOR. An LLM-driven decision would be
non-deterministic (the same inputs give different answers on different days),
expensive at deal-flow volume, hard to test, and impossible to explain in the
terms a fund actually uses — "this cleared our threshold" rather than "the model
felt good about it".

But a purely mechanical rule set also fails: strong-but-off-thesis companies,
contested reviews, and thin evidence are exactly the cases where a threshold is
the wrong instrument.

## Decision

The partner engine is rule-based by default. Thresholds come from the active
partner-rules version (ADR-0002) combined with the fund configuration, with
ordering-invariant clamps so evaluation order cannot change the outcome.

The LLM is invoked **only** for the edge-case triggers declared in the active
partner rules file, and `PARTNER_USE_LLM` can disable even that. Where an LLM
result is used, it produces rationale and decision drivers; it does not override
the canonical score thresholds.

Related consequences of the same principle:

- Reviewer scoring is deterministic and structured, with confidence discounting
  and a persisted scoring trail.
- A mandate-fit gate holds strong-but-off-thesis deals for an explicit IC
  exception rather than auto-passing them.
- Weak or contested evidence sets `human_review_required` instead of resolving
  the ambiguity with a model call.

## Consequences

**Good.** The same inputs produce the same decision. Decisions are explainable in
fund vocabulary. Cost per deal is bounded and predictable. Rule behaviour is
directly testable — `tests/evaluation_v2/test_partner_rules_contract.py` and the
golden sets under `resources/evaluation/golden_set/` do exactly that.

**Cost.** Rules cannot express genuinely novel situations; those become
escalations, which is more human work than a model that always answers. Threshold
tuning is a policy-publishing exercise rather than prompt editing.

## Alternatives considered

- **LLM-as-partner.** Non-deterministic, expensive, untestable at this
  granularity, and the failure mode is a confident wrong answer.
- **Pure rules, no LLM at all.** Loses useful rationale on genuine edge cases.
  The narrow, declared trigger set is the compromise.
