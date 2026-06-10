# Aethria — Product Direction

*The operating model behind the application architecture. `DESIGN_SYSTEM.md` governs tokens
and components; this document governs what the product **is** and why the screens are
shaped the way they are.*

---

## What Aethria is

Aethria is not a CRM, a dashboard, or a database of startups. It is an **investment
operating system**: an autonomous pipeline (scouts → reviewers → partner → portfolio →
meta) with a human principal. The product's job is to put the principal in command of
that instrument — never to show them "features."

The design reference is Dieter Rams through a modern software lens: a precision
instrument, not a web application. Every screen must answer one question — *"does this
feel like a dashboard full of features, or a tool built with absolute clarity of
purpose?"*

## The operating states

An investor using Aethria is always in exactly one of six states. The architecture maps
one place to each state; nothing else earns top-level presence.

| State | Place | Route |
|---|---|---|
| Arriving — what happened, what needs me | **Today** | `/v1` |
| Judging — ruling on what the system surfaced | **Flow** | `/v1/flow` |
| Researching — pulling a specific company through the machine | **Dispatch** | ⌘K, from anywhere |
| Monitoring conviction — the book, the watchlist, the signals against them | **Portfolio** | `/v1/portfolio` |
| Steering the instrument — mandate, record, patterns, calibration, evolution | **Fund** | `/v1/fund` |
| Configuring — thresholds, identity, operations | Settings | `/v1/settings` |

Settings renders inside the same frame as the workspaces — the spine never leaves.
There is exactly one full-screen surface in the product: the Dispatch takeover.

What this replaced: a single mega-workspace whose modes (Workspace / Judgements /
System) swapped panels in place, plus a six-tab "Intelligence" panel. **Intelligence is
not a place** — it was a bucket of leftovers. Its surfaces were redistributed by what
they say, not where their data comes from:

- *Signals* → Portfolio (signals act on conviction; they are not meta-commentary)
- *Resolutions* → Fund › **Record** (the ledger of human judgment)
- *Analytics* → Fund › **Patterns** (what the instrument's decisions reveal)
- *Thesis* → Fund › **Mandate** (what the instrument hunts)
- *Calibration* → Fund › **Calibration** (how tightly it is tuned)
- *Meta* → Fund › **Evolution** (how it rewrites itself)

Scout allocation and weights live in Fund › Evolution — scouts are part of the
instrument, not a destination.

## The spine

The full-height oxford (navy) rail is the product's identity and is constant on every
workspace. It carries exactly five things and nothing else:

1. **Identity** — wordmark (always `paper` on oxford chrome, verdigris dot), clock.
2. **The places** — Today, Flow, Portfolio, Fund (keys 1–4), Dispatch (⌘K).
3. **Judgment pressure** — the one number that needs the human (escalations, in
   escalation tone) or the open count when nothing does; pipeline state as a single
   word (LIVE / IDLE / OFF / ISSUE).
4. **The mandate** — the active thesis the entire pipeline is gated on. One line.
5. **The operator** — who is signed in, settings, log out.

If a candidate element for the spine is not one of these five, it belongs to a
workspace.

## Today

The desk — the arrival surface and the home route. It states the situation in one line
("3 matters require your ruling · 5 new arrivals"), then briefs: what requires
judgment, what arrived, the latest judgments, the signals moving, the instrument's
state. It is a **briefing, not a dashboard**: lists and readouts, no stat boxes, and
every line is a doorway into the workspace where the work happens. If it cannot change
what the principal does next, it does not appear here.

Today also absorbed the "While you were away" interstitial: what the agents did since
the last visit is one quiet line in the briefing header, not a full-screen gate the
principal must dismiss before reaching their desk.

## Flow

Two columns beside the spine, split on the golden ratio: the queue (38.2%) and the open
memo (61.8% — it is a document; it gets the measure).

The defining decision: **the workspace is never blank.** When no memo is open, the right
column rests on the live judgment record (Judgements) — the instrument keeps reporting
while the principal scans the queue. Empty states that instruct the user ("select a
matter to open the memo") are replaced by states that *inform* them.

Deep links: `/v1/flow?open=<id>` opens a memo (used by Today, Dispatch results,
Portfolio, and Fund); `/v1/flow?queue=escalated|new` focuses a queue view (used by the
spine's pressure readouts). Legacy `/v1?open=…` links redirect into Flow.

## Dispatch

The ⌘K takeover is the design anchor for the whole system — progressive disclosure,
one purpose, zero chrome. It is intentionally untouched, and it is now **global**: its
state lives in the app frame, so a lookup started anywhere survives navigation and its
result toast can be acted on from any workspace.

## Portfolio

Conviction monitoring, composed in one line of sight: book composition as bare
instrument readouts (numbers + labels, no boxes), the conviction book, concentration,
the watchlist with its time pressure, and the signals moving against all of it. Every
row navigates to the company's memo in Flow.

## Fund

The instrument itself. Header: the fund's name, mandate version, and its three live
alignment readouts. Body: the five facets (Mandate, Record, Patterns, Calibration,
Evolution) in the order an investor reads an instrument — what it hunts, what was
ruled, what its decisions show, how tightly it is tuned, how it rewrites itself.

## Rules of composition

These extend `DESIGN_SYSTEM.md` from tokens to layout judgment:

- **Hierarchy over decoration.** A number with a mono label above a hairline outranks
  any card. Boxes are a last resort, not a default container.
- **Numbers are readouts.** Large, mono, tabular, semibold; their labels small,
  uppercase, muted. The number is the content; the label is the engraving.
- **One escalation color, two surfaces.** `escalation` on paper, `escalation-bright`
  on oxford chrome — both reserved for states requiring a human.
- **Whitespace must create focus.** The golden-ratio splits and Fibonacci gaps are the
  grid; if removing an element does not lose information, remove it.
- **Everything addressable.** Every place has a URL; every readout that implies an
  action navigates to where the action happens.
- **The instrument reports; the human rules.** Copy is declarative ("3 need ruling"),
  never promotional, never instructional unless the system is unconfigured.
