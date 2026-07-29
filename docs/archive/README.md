# Archive — historical records

Everything in this directory is a **point-in-time record**. It describes what was
true, planned, or believed on the date it was written. It is not a statement of
current behaviour, and several findings here have since been fixed.

**Do not edit these files.** Do not cite them as current. For the current
position:

| For | See |
|---|---|
| How the system works now | [../../ARCHITECTURE.md](../../ARCHITECTURE.md) |
| Open technical debt | [../../ROADMAP.md](../../ROADMAP.md) |
| Open defects | [../known-issues.md](../known-issues.md) |

## Contents

| Directory | What it holds |
|---|---|
| `audits/` | Codebase, UI, and diagnosis audits from 2026-06 and 2026-07. The 2026-07-14 full audit lists five ranked bugs; all five were verified fixed in the current source during the 2026-07-29 documentation pass |
| `plans/` | Implementation plans and per-change planning ledgers, including the investor-value feature roadmap that informs [ROADMAP.md](../../ROADMAP.md) |
| `specs/` | Per-change design specifications, mostly frontend. Some cite design prototypes now at `docs/design/explorations/` |
| `institutional-foundation/` | Phase 0–8 readiness certifications for the canonical identity/evidence/decision layer |
| `product/` | Early PRD artefacts from the Phase 1 MVP |

## Why keep it

The reasoning behind past decisions is often more useful than the decision
itself, and these documents record trade-offs that would otherwise have to be
rediscovered. Decisions that are still load-bearing have been promoted to
[ADRs](../adr/); the rest lives here.
