# ADR-0006 — A canonical identity, evidence, and decision layer

**Status:** Accepted

## Context

The original model was one flat `startups` row per discovery, carrying scout,
review, and partner payloads inline. It worked for a single autonomous pipeline
and broke as soon as the same company could arrive more than once — a scout
discovery, a manual lookup, a CSV import, a referral — and as soon as decisions
had to be defensible.

Three specific gaps: the same real company produced several unrelated rows with
no notion of a canonical entity; claims about a company had no provenance, trust
class, or verification state, so a model's assertion looked identical to a
verified filing; and a recommendation could be overwritten in place, leaving no
immutable record of what was decided under which policy.

## Decision

Build a canonical domain alongside the legacy model, and migrate behind an
explicit rollout mode rather than swapping it in.

- **Identity** (`identity/`) — source observations normalise into canonical
  `companies` and `opportunities`. A confident match links; an ambiguous one
  opens an `identity_case` for a human. The system never silently merges two
  companies.
- **Evidence** (`evidence/`) — artifacts, claims, and claim↔evidence links, each
  with trust class, verification state, assertion class, and access class.
  Confidential material carries a retention policy. Corrections append; they
  never overwrite. Ingested third-party text is screened for prompt injection.
- **Evaluation** (`evaluation_v2/`) — immutable evaluations bound to a policy
  version and an evidence snapshot, with explicit prerequisites that fail closed.
- **Decisions** (`decisions/`) — the human ruling is authoritative. Workflow
  actions and approvals hang off it; an approval records intent and does not
  itself perform an external write.
- **Authority** (`authority/`) — the rollout state machine:
  `legacy → shadow → backfill → canonical_write → canonical_read`, with
  reconciliation, projection replay, and rollback exposed under
  `/api/authority/*`. Workflow states and block codes are enums.

## Consequences

**Good.** One company, one canonical record, regardless of how many ways it
arrived. Every claim carries provenance. Decisions are reproducible against a
named policy and a fixed evidence set. The cutover is reversible at every step
and observable through reconciliation.

**Cost.** Two data models coexist for the duration, with a compatibility
projection keeping legacy read models populated — a real and ongoing tax, tracked
as debt item D2 in [ROADMAP.md](../../ROADMAP.md). The canonical path needs a
direct PostgreSQL connection, so it is unavailable in the file-storage dev mode.
Ambiguity now surfaces as human work that the old model hid.

## Alternatives considered

- **Big-bang cutover.** No safe rollback for a change that touches every write.
- **Retrofit identity onto `startups`.** Would not have given immutable
  evaluations or an evidence ledger, which are the parts that make a decision
  defensible.
