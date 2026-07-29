# ADR-0010 — Fail closed on missing thesis, ambiguous identity, or thin evidence

**Status:** Accepted

## Context

Every stage of this system can produce a plausible-looking output from inadequate
input. A reviewer with no fund thesis will still return five scores. An evaluator
pointed at the wrong company will still write a memo. A scoring engine given two
weak sources will still emit a number to one decimal place.

Each of those is worse than an error, because it is indistinguishable from a good
result at the point where someone reads it — and this product exists to be
trusted with investment decisions.

## Decision

Where input is inadequate, block with a named reason rather than degrade.

| Gate | Behaviour |
|---|---|
| No active fund thesis | The periodic pipeline skips the cycle, logs a warning, and returns. On-demand lookup still runs — it is mandate-aware but never thesis-blocked, because a user asking about a named company should always get an answer. |
| Ambiguous company identity | An `identity_case` is opened for human resolution. No silent merge, no best-guess match. |
| Missing evaluation prerequisites | `EvaluationPrerequisiteError`. A thesis-blind or evidence-thin evaluation does not run. |
| Thin evidence / contested reviews | The pipeline continues but marks handoff quality and can set `human_review_required`. |
| Missing `OPENAI_API_KEY` | Pipeline skipped immediately with a logged reason — never a silent no-op. |
| Unapplied migrations | A loud `SCHEMA DRIFT` warning at startup naming the missing columns, because the write path otherwise drops unknown fields silently. |
| Production without an event backplane | Startup raises, unless single-instance operation is explicitly acknowledged (ADR-0004). |
| Blocked durable job | Explicit `BlockCode` on the job row, surfaced through `GET /api/jobs`. |

Warnings are persisted rather than dropped: weak sources, missing data,
contested reviews, and low confidence stay visible in the agent trace instead of
disappearing between stages.

## Consequences

**Good.** A stalled deal always says why. The absence of an answer is
distinguishable from a bad answer. Operators can act on named blocks.

**Cost.** More visible failure states, more human work in the queue, and more
paths where a user sees "blocked" instead of a result. New features must decide
their gate behaviour explicitly rather than inheriting a permissive default.

## Alternatives considered

- **Degrade gracefully with a confidence score.** Confidence attached to a
  fabricated answer is still a fabricated answer, and it gets read as a result.
- **Fail closed everywhere, including lookup.** Rejected: a user who names a
  company should not be told to write a fund thesis first.
