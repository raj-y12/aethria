# ADR-0012 — The investment read is narrative, and never a score input

**Status:** Accepted

## Context

Aethria's reviewer expresses the whole of its judgement about a team as one
ordinal component, `execution.team_execution`, anchored on a credential ladder
(`elite` → `weak`). That ladder answers "how impressive is this founder", which
is not the question a good investor asks. The question is what the founder's
background makes *cheap*: which problems they are fluent in, whose calls get
returned, which market they can enter without retraining. A rank cannot hold a
mapping.

Two related reads were also unrepresentable. Nothing asked what the hardest
instance of the problem the product *demonstrably* handles is, and therefore
what is downhill of it — the five dimensions score the market the company
states, not the capability it has shown. And nothing let the reviewer say that
the obvious question about a company is the wrong question.

The pressure to bolt these onto the score layer is real and should be resisted:
scores are versioned, threshold-bearing policy (ADR-0002), and the read is an
LLM narrative with no objective anchor. Mixing them would let prose move a
verdict.

## Decision

- Three reviewer output fields carry the read: `founder_fluency`,
  `capability_slope`, and `reframe`. They are narrative only. No field feeds a
  score, a confidence, a component label, or a verdict threshold.
- The doctrine that governs them — purpose, evidence bar, and the omission rule
  for each field — is versioned policy data in
  `resources/config/reviewer_rules/`, introduced in `v2`. On `v1` the fields are
  never requested and never emitted, so the read is a policy rollback away from
  being off. `v2` carries `verdict_thresholds` and `diligence_red_flags`
  unchanged from `v1`; a test pins that.
- The read fails closed (ADR-0010). `founder_fluency` is restricted to founders
  the identity layer actually resolved and each entry must name the employer,
  role, or publication it rests on. `capability_slope` requires a demonstrated
  hardest instance *and* something downhill of it — a roadmap is an ambition,
  not a slope. `reframe` is all three parts or none. Anything short is dropped,
  never completed by inference.
- Emptiness is a correct and common answer. The full memo prints the named
  absence so a reader can tell "no read" from "read not attempted"; the display
  memo omits the section entirely.
- The read is produced by the primary reviewer persona only. Skeptical and
  Opportunist reviewers exist to diverge on evidence, not to each write prose
  (ADR-0009 economics).

## Consequences

The memo gains a lead that says something the scores structurally cannot, and
the score layer is untouched — which matters because the scoring layer is the
part we least trust today. Improving the read and improving the scores are now
independent workstreams.

The cost is a new hallucination surface. The evidence bar, the resolved-founder
restriction, and the existing founder grounding guard are what hold it; the
failure mode to watch is not a wrong score but a confident adjacency with no
named source behind it. Reviews on thin scouts will show an empty read. That is
the system working.

## Alternatives considered

**Extend the `team_execution` anchor ladder with richer rungs.** Rejected: more
rungs still rank. The read is relational, and forcing it ordinal would corrupt
a rubric that deterministic scoring depends on.

**Let the slope raise the defensibility score.** Rejected for now. The scoring
layer is the least trusted part of the system; wiring unvalidated narrative into
it would make both harder to debug. Revisit once reads have been reviewed
against real decisions.

**Ship it as prompt guidance without a policy version.** Rejected: it would put
evaluation doctrine in Python, which invariant 3 forbids, and leave no way to
turn the read off without a deploy.
