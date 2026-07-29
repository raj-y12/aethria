# ADR-0002 — Investment decision policy is versioned data, not code

**Status:** Accepted

## Context

The partner stage converts scores and evidence into INVEST / PASS / MONITOR.
Those thresholds are the product: they change as a fund's mandate changes, they
differ between funds, and when a decision is questioned months later the answer
must be "under the policy in force at the time, this is what it produced."

Thresholds embedded in Python would make every mandate change a deploy, make
per-fund variation impossible without branching logic, and leave no way to state
which rules a past decision was made under.

## Decision

Decision policy lives in versioned JSON, resolved at runtime.

- `resources/config/partner_rules/v{1..4}.json` hold thresholds and the triggers
  that permit an LLM call.
- `resources/config/active.json` names the live version for each policy family
  (partner rules, reviewer rules, evaluation rubric, fund thesis default).
- `backend/core/policy_resolver.py` resolves the active version at runtime;
  `POST /api/policy/reload` refreshes the cache without a restart.
- Reviewer rules, the evaluation rubric, and contract schemas under
  `resources/contracts/` are versioned the same way.
- For per-fund configuration the governed path applies:
  `services/scoring/policy_compiler.py` compiles a fund configuration into a
  policy, it is previewed against bound content hashes, and publishing writes an
  immutable `governed_policy_version` row. Evaluations reference the version that
  produced them.

## Consequences

**Good.** Mandate changes are data changes. Decisions are reproducible against a
named policy version. Per-fund variation needs no branching code. Policy changes
can be previewed and reviewed by a human before they take effect.

**Cost.** Two places to look when reasoning about a decision — the Python that
applies the rules and the JSON that supplies them. A malformed policy file is a
runtime failure rather than a type error, so `test_partner_rules_contract.py`
and the policy compiler's validation carry real weight.

## Alternatives considered

- **Thresholds as environment variables.** Cheaper, but unversioned, untestable
  as a set, and impossible to attach to a historical decision.
- **Full rules engine / DSL.** More expressive than needed. The rule set is small
  and the JSON schema plus contract tests cover it.
