# Settings Simplification — One Page, Two Registers

**Date:** 2026-07-09
**Scope:** `app-front-end/src/settings/SettingsPage.tsx` (single file; no routing or API changes)
**Status:** Approved direction (option A); pending spec review
**Driver:** Pilot-user feedback — the settings page is far too complex.

## Problem (measured)

One ~5,400px scroll, 7 sections, 32 inputs + 23 chip toggles ≈ 55 decisions.
Two audiences are interleaved: investor decisions (fund mandate, memo
verbosity, ruling toggles) sit between system-tuning knobs (scoring weights,
decision thresholds, runtime/budget gates). Worse, some content is inert:

- **Rubric / "Evaluation Framework"** (1,047px) self-describes as
  "read-only reference" — documentation, not settings.
- **Risk "Penalty weights"** — four `disabled` number inputs badged
  "Display only".

FundPage's "Edit mandate →" links here, so for a pilot user the mandate is
the page's real payload; everything else is noise around it.

## Design

Same route (`/v1/settings`), same spine-nav pattern, restructured into two
registers.

### Investor register (visible by default, in order)

1. **Fund Mandate** — unchanged content (fund/mandate name, stages,
   geographies, sectors, business models, …).
2. **Memo Output** — unchanged (2 inputs).
3. **Ruling** — the two risk UX toggles only (`Require acknowledgement
   before ruling`, `Only gate high severity risks`), retitled from
   "Adverse / Risk Sensitivity" to plain "Ruling". The escalation-sensitivity
   select moves to System tuning — it tunes engine behaviour, not the
   ruling experience.

### System tuning (one collapsed disclosure at the end)

A single quiet editorial disclosure — kicker `SYSTEM TUNING`, one line of
copy ("Engine internals: scoring weights, decision thresholds, and runtime
limits. Defaults are sensible.") — collapsed by default, expanding to:

4. **Scoring Weights** — unchanged (5 inputs).
5. **Decision Thresholds** — unchanged (5 inputs).
6. **Operations** — unchanged (4 inputs: batch caps, budget, cooldowns).

Expansion state is component-local (no persistence). Spine section nav
shrinks from 7 items to 4: Mandate, Memo, Ruling, System tuning. Clicking
"System tuning" in the nav expands the disclosure and scrolls to it.

### Deletions (no replacement)

- The **Evaluation Framework / rubric section** and its
  `DimensionFrameworkCard` component. If the scoring-scale reference is
  missed, it can be resurrected in the Fund workspace later.
- The **four disabled penalty-weight fields** and their "Display only"
  badge, plus the now-dead draft fields
  (`missingFounderPenalty`, `missingTractionPenalty`,
  `contradictionPenalty`, `weakSourcePenalty`) from the UI. On save, these
  fields are passed through from the loaded settings object unchanged —
  the API payload shape and stored values are untouched.
- The header disclaimer sentence about display-only controls (no longer
  true once the fakes are gone).

### Expected result

~2,300px default scroll, ~30 controls visible (mostly the mandate's
meaningful chips), zero inert controls, engine internals invisible until
summoned.

### Explicitly out of scope

- No routing changes, no `/settings/advanced`, no admin relocation.
- No changes to `api/settings.ts` types or backend.
- No redesign of the mandate section's fields.
- No persistence of the disclosure's open state.

### Verification

- `tsc`, eslint, existing test suite.
- Screenshot-harness checks (route `/v1/settings`): default view (system
  tuning collapsed), expanded view, spine nav shows 4 items, mobile width.
- Save round-trip still works against the mock (draft → save button state).
