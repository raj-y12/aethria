# Investor-Value Feature Roadmap — What Would Make VCs Fight to Use Aethria

**Date:** 2026-07-14
**Premise:** VCs don't pay for "AI evaluates startups." They pay for four things: **sourcing edge** (see deals others don't, earlier), **diligence speed** (conviction in hours, not weeks), **calibration** (proof their judgment — and the fund's process — is getting better), and **LP optics** (a defensible, reportable process). Every feature below is ranked by how hard it hits one of those four, and by how much of it Aethria's existing machinery already provides.

A deliberate observation from the audit: the pipeline's strongest asset is not the scouts inventing companies — it's that we have a **full evaluation engine with versioned theses, deterministic scoring, decision history, and per-deal provenance**. The features that win are the ones that point that engine at *the deal flow VCs already have* and at *the outcomes of decisions already made*.

---

## Tier 1 — Fight-in-line features (build these)

### 1. Anti-Portfolio Tracker — "what happened to everything you passed on"
**The hook:** every VC has a haunted anti-portfolio (Bessemer publishes theirs). Nobody has tooling for it.
**What it does:** every PASS and expired MONITOR is silently tracked. The signal tracker (already built, `portfolio/signals.py` + Tavily) watches for subsequent funding rounds, launches, and acquisitions. When a passed company raises, the fund gets a card: *"You passed on X (scored 6.2, 'weak defensibility') — they closed a $12M Series A led by Accel 9 months later."* Aggregated over time this becomes the **calibration scoreboard**: hit rate, miss patterns by sector/dimension, "your skeptical reviewer was wrong about moats 4 times running."
**Why they fight for it:** it's the only honest feedback loop in venture, it's emotionally magnetic, and the data compounds — switching away means abandoning your calibration history. This is the retention moat.
**Builds on:** watchlist/signal infra, `conviction_state.decision_history`, `meta_mutation_log` (human vs AI disagreement is already recorded per escalation), rejection analytics.
**New work:** extend SignalTracker to rejected/passed rows (it only watches the watchlist today), an outcomes table, one digest surface. Medium effort.

### 2. Inbound Ingestion — forward a pitch deck, get an IC-grade memo
**The hook:** scouts *finding* companies is a demo feature; a VC's real firehose is **inbound** — decks, intro emails, DocSend links. Today Aethria makes them retype a company name into Dispatch.
**What it does:** each fund gets an ingest address (`deals@<fund>.aethria.app`) and a drag-and-drop drop zone. A deck/email becomes a scout payload (PDF → extraction → `ScoutInfo`, with the deck's own claims marked as founder-asserted vs. externally verified by the existing reference verifier), then flows through the normal reviewer → partner → memo pipeline. The memo's evidence ledger distinguishes "deck claims" from "verified externally" — that contrast IS the diligence product.
**Why they fight for it:** it converts their largest, most annoying workload (triaging 100+ inbound decks/month) into a ranked, thesis-scored queue by the next morning. This is the acquisition feature — the demo where a partner forwards a real deck and gets a real memo is the one that closes.
**Builds on:** the entire pipeline, `additional_context` operator-evidence path (already shipped end-to-end), reference verification, `operator_context` untrusted-evidence handling on `ScoutInfo`.
**New work:** email ingress + PDF extraction + claim/verification tagging. Large-ish but almost entirely at the edge; the core pipeline is untouched.

### 3. Thesis Backtesting — "replay my deal flow under the new mandate"
**The hook:** changing a fund thesis is a leap of faith. Aethria can make it an experiment.
**What it does:** before publishing a thesis edit, Settings shows: *"Under this mandate, of your last 214 deals: 9 PASSes become INVEST, 3 INVESTs fall outside thesis, avg alignment shifts +0.14. Here are the 9."* Publish then optionally reprocesses for real.
**Why they fight for it:** nobody else can do this — it requires exactly what Aethria already has: versioned theses, per-deal thesis-alignment scores stamped with `fund_thesis_version_id`, deterministic (LLM-free) scoring and partner rules that can be re-run cheaply, and a reprocessing pipeline (`reprocess_startups_missing_fund_thesis` is 80% of the machinery). It turns the mandate editor from a form into an instrument, and it makes thesis iteration — the thing partners argue about at every Monday meeting — quantitative.
**Builds on:** `fund_thesis_versions`, `DeterministicScoringEngine`, `partner_rules`, policy compiler, the existing reprocess endpoint.
**New work:** a dry-run mode that re-scores in memory against a draft thesis without persisting, plus a diff UI in Settings. **This is the highest wow-per-line-of-code item in the doc.** Small-to-medium effort.

### 4. LP-Ready Process Reporting — the funnel, one click
**The hook:** emerging managers live or die on convincing LPs they have a *repeatable process*. Aethria literally is one, and already records every stage transition.
**What it does:** a quarterly export (PDF/deck-ready): deals sourced → reviewed → IC'd → invested, by sector/stage/geography; thesis-alignment drift across the quarter; time-to-decision; human-override rate vs AI recommendation; anti-portfolio outcomes (feature 1 feeds this). Branded with the fund identity already in settings.
**Why they fight for it:** it converts Aethria from a tool a partner likes into something the *fund* institutionally depends on for fundraising. LP reporting is a chore with a deadline — deadline-driven chores sell software.
**Builds on:** `pipeline_activity`, `scoring_trails`, `conviction_state`, thesis alignment stats (`compute_thesis_alignment_stats`), the existing PDF export path.
**New work:** aggregation queries + one well-designed report template. Small-medium effort, mostly design.

---

## Tier 2 — Strong differentiators (next)

### 5. IC Mode — multi-partner votes on escalations
Escalations today are ruled by one user. Real funds decide in committee. Give escalations a vote stage: each partner rules independently (blind first, like the three reviewer personas), disagreement is surfaced the same way reviewer disagreement already is, and the conviction history records who voted what. **This requires the org/team tenancy model — the single biggest architectural unlock in the codebase** (`user_id` → `fund_id` + members). Worth doing as its own project; every Tier-1 feature gets more valuable once a whole partnership is in the product.

### 6. Follow-on & Portfolio Momentum Radar
Portfolio tracking exists (execution/signals/health) but answers "is anything wrong?" VCs also need "who deserves the next check?" Score portfolio momentum from signals (hiring velocity, launches, round rumors) and rank reserve-deployment candidates. Builds directly on the signal tracker once Bug 3 from the audit (signals read from local files) is fixed.

### 7. Founder Dossiers
The company resolver already extracts founder names and LinkedIn/Crunchbase URLs. Extend one stage: prior companies and exits, tenure history, technical footprint (GitHub/publications) for technical founders — rendered as a memo section. High perceived diligence value, bounded scope because the resolver's evidence machinery already exists.

### 8. Shareable Deal Rooms
A memo becomes a private, expiring share link for co-investors/syndicate partners (redaction controls: hide scores/rationale, show profile+evidence). Every share is a viral loop — the recipient VC sees the memo quality with the Aethria wordmark on it. Small backend (signed share tokens, public read-only memo route), careful product thinking on what's shareable.

---

## Tier 3 — Explicitly deprioritized (and why)

- **Warm-intro network graph** ("who can intro me") — needs the partner's email/LinkedIn graph; heavy integration surface, privacy-sensitive, and other products (Affinity) own it. Don't fight there.
- **CRM features** (pipeline stages, reminders, notes-first workflows) — becomes an Affinity/Attio clone and dilutes the "autonomous evaluation" identity. Integrate (push decided deals *to* their CRM via webhook) rather than replicate.
- **More scout personas / more LLM commentary** — the audit showed evaluation quality machinery is already deep; adding a fifth persona adds cost, not conviction. Value now comes from *inputs* (feature 2) and *outcomes* (feature 1), not more synthesis.

---

## Sequencing recommendation

1. **Thesis Backtesting (3)** — smallest build, biggest demo moment, zero new data sources.
2. **Anti-Portfolio Tracker (1)** — starts accruing outcome data immediately; every month of delay is calibration history lost forever. Ship the tracking write-path early even if the UI comes later.
3. **Inbound Ingestion (2)** — the acquisition wedge; build once 1+3 give the demo its "and it learns" ending.
4. **LP Reporting (4)** — quarter-end aligned; ship before a quarter boundary.
5. **Org tenancy → IC Mode (5)** — the platform bet that multiplies everything above.

The through-line: Aethria stops being "an AI that finds startups" and becomes **the fund's institutional memory** — every deal seen, every decision made, every outcome tracked, every thesis change measured. That's the product VCs can't leave.

---

## Frontend impact

Tier 1 is deliberately backend-heavy; the frontend work extends existing surfaces rather than adding architecture. Per feature:

| Feature | Surface | Frontend work | Size |
|---|---|---|---|
| **3. Thesis Backtesting** | Settings — deploy flow | Impact panel inside the existing `FundThesisConfirmationModal` ("9 PASS → INVEST, 3 INVESTs fall outside thesis" + click-through list). One client fn in `api/fundThesis.ts`, one panel component. No new route. | S |
| **1. Anti-Portfolio** | Home briefing + Portfolio page + memo | New digest card type in the existing `sinceAway` pattern (stays a briefing, not a dashboard); an "anti-portfolio ledger" register on the Portfolio page in its existing list idiom; an outcome banner on memos of passed deals. New query hook + types; SSE nudge reuse. | M |
| **2. Inbound Ingestion** | Dispatch + memo | Drop-zone/attach on `DispatchCommandBar`; an ingested deck is a lookup whose input is a file, so `useDispatchLookup`'s queued/pending states already model it. Real new UI: the evidence ledger (`evidenceLedger.ts` / `InvestmentMemoContent`) must typographically distinguish founder-asserted deck claims from externally verified facts — a natural fit for the broadsheet language. Overnight triage is a sort/badge on WorkGrid, not a new grid. | M–L |
| **4. LP Reporting** | Fund workspace | Quarter picker → report preview → PDF download panel; Fund page already hosts meta/analytics and PDF export exists. Mostly design. | S–M |
| **5. IC Mode** (Tier 2) | Everywhere | The one real architecture change: Clerk orgs in the auth shell (`App.tsx` cache-clear-on-user-switch becomes org-aware), voting UI on `DecisionStage`/escalations, member management in Settings, attribution throughout. Sequenced last for exactly this reason. | XL |

Cross-cutting: each feature adds a query hook + `types/startup.ts` types; only the anti-portfolio digest joins the warm-start first-paint keys; new surfaces must hold the paper-editorial line — backtest diffs and LP funnel tables are where the broadsheet aesthetic works *for* us rather than against.
