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

Inside the working rooms (Flow, Portfolio, Fund, Settings) the spine is constant and
is the product's **only rail**. A room may take over its contextual regions (Settings
projects its section nav and draft/save state into it, with a "← Today" exit);
identity stays at the top and the operator at the bottom, always. Never a second
sidebar beside the spine. Two surfaces are deliberately chrome-free — the front door
(Today) and the Dispatch takeover — both centered, both speaking in serif.

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

## Today — the front door

The home route is modelled on the Dispatch takeover, which is the product's voice:
**no sidebar**, one centered column on dotted paper, staggered upward reveals. Top to
bottom: the wordmark; the date as a tracked mono eyebrow; **the system speaking in
Playfair** — one situation headline ("3 matters await your ruling." / "The desk is
clear."); a quiet counts line (plus the since-away report); then **the four doors as
control keys in the middle of the canvas** — Flow is the single solid oxford key (the
product's one action is making judgments), Portfolio / Fund / Dispatch are quiet
ghosts, each carrying its live reading. A Dispatch-style micro-action footer holds the
operator, mandate, settings, and log out.

The serif headline is the personality register: when Aethria addresses the principal
(the front door, the Dispatch takeover, login), it speaks in Playfair. Inside the
workspaces, the instrument is sans and mono — but **every room opens in the voice**:
a `RoomHeader` with a tracked mono eyebrow and a Playfair title ending in the
verdigris period (the wordmark's punctuation is the product's signature —
"Portfolio." / "How this fund thinks."). The Decision Stage sets the company name in
the same serif, so the subject of a judgment is addressed the way the Dispatch result
addresses it.

## Flow

**Queue | active decision.** The queue (34%) is compressed utility — small type, dense
rows, selection read through weight and full ink, never size. The right column (66%) is
the **Decision Stage**: the active company owns the canvas with the one act the product
exists for — make a judgment — given real gravity:

- a huge conviction numeral (counts up on arrival) over a tiny `/100 conviction` scale
- the state of the call in bold mono — `NEEDS YOUR RULING` in escalation ink is the
  product's moment of tension
- the company name at display scale, one standfirst line
- the instruments: thesis-fit track, the reviewer **agreement map** (each reviewer's
  mean as a tick on the 0–10 axis; split reads in escalation ink), partner confidence
- "What decides it" — the focal question — then the full memo flowing beneath

The stage always has a subject: the top of the current queue view takes the canvas
automatically (without being acknowledged — only a deliberate click marks a row seen).
There is no empty resting state and no Close: a different row replaces the subject.
This is the layout's compression/release rhythm: dense list → silence → huge score →
small metadata.

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
- **Verdict chips are the system's one colour accent.** Soft-fill pastel chips
  (sage INVEST, butter MONITOR, clay PASS) make verdicts scannable at a glance —
  they are the deliberate exception to monochrome, and the only one. No new hues
  beyond this ramp; burgundy remains reserved for states requiring a human.
- **One selection language.** Vertical lists (spine nav, queue rows) mark the current
  item with a 2px left bar; horizontal tabs (Fund facets) with a 1px underline. Never
  both, never a filled pill. The left bar marks selection only — it is not an alarm
  channel.
- **Everything addressable.** Every place has a URL and a named browser tab
  ("Flow — Aethria"); every readout that implies an action navigates to where the
  action happens.
- **The instrument reports; the human rules.** Copy is declarative ("3 need ruling"),
  never promotional, never instructional unless the system is unconfigured.
