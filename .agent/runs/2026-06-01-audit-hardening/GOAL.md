# Audit hardening UX

Goal ID: `2026-06-01-audit-hardening`
Started: 2026-06-01T11:11:50Z
Parent goal: 2026-06-01-product-audit
Mode: full
Ledger path: `.agent/runs/2026-06-01-audit-hardening/`

## Objective

Ship remaining ruthless-audit items: opt-in agents/activity, settings 3-step nav, system panel split, scoring narratives, remove autonomous copy.

## Goal Mode Coupling

When creating or updating the matching `/goal`, include this ledger pointer in the goal objective:

`Maintain the agent-owned ledger at /Users/rajyendamuri/aethria/.agent/runs/2026-06-01-audit-hardening/ and keep implementation-notes.html current at checkpoints, before compaction, and before final handoff.`

## Finishing Criteria

- [todo] Define concrete validation before implementation.
- [todo] Keep `implementation-notes.html` current with status, decisions, tradeoffs, changes, validation, and next action.
- [todo] Link large proof artifacts from `evidence/` when they are too bulky for the HTML notes.

## Escape Hatch

Pause, ask the user, or mark a scoped item `[blocked]` / `[incomplete]` if:
- validation contradicts the goal
- the goal requires a scope change
- the agent is looping without measurable progress
- the next step risks deleting or rewriting durable memory
- the PRD and actual repo disagree
- the ledger itself contaminates validation

