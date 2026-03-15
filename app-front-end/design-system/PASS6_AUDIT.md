# Pass 6 — App audit: panels, empty states, loading, copy

Inventory of every panel, tab, empty state, loading state, and system copy to frame additions for Pass 6.

## Panels and tabs

| Area | Panels/tabs | Empty when |
|------|-------------|------------|
| **MainLayout** | Left column: wordmark, status strip, WorkGrid. Right: Judgements / System / Memo. | Right panel empty when no panel selected. |
| **WorkGrid** | Single list of deal rows. | `startups.length === 0` — currently shows "SCOUTS RUNNING" + "FIRST DISCOVERIES EXPECTED IN ~5 MINUTES". |
| **LiveIntelligenceFeed** (Judgements) | Chronological log of scanned, reviewed, decision, signal, meta-cycle, escalation-resolved. | `entries.length === 0` (no startups/signals/meta yet) — **no empty state**; bare panel. |
| **SystemIntelligence** | Tabs: Meta, Signals, Escalations, Analytics. | Signals: "No signals detected". Escalations: "No pending escalations". Analytics: "No rejection data yet", "No pipeline data yet", "No cycles completed yet". Meta: "No cycles completed yet". |
| **Settings** | Tabs: Account, Budget, Pipeline, Discovery, Meta, Portfolio. | Budget: when `system_health.budget_status.length === 0` — no "current usage" section; inputs can be empty/zero with no framing. |
| **Investment memo** | Header (label, company, sector) then scrollable body (judgment, overview, drivers, decision). | N/A (only shown when a startup is selected). |

## Loading states

| Context | Current behaviour | Note |
|---------|-------------------|------|
| **App boot** | `LoadingAnimation` full-screen until `isLoaded` and `tokenReady`. | Correct; keep as only full-screen loader. |
| **Settings page** | `LoadingAnimation` full-screen until `fetchSettings()` resolves. | Should become panel-level skeleton inside Settings chrome. |
| **Dashboard (MainLayout)** | No explicit loading; `useSystemData` returns empty arrays until first poll completes. | No skeleton; data just appears. Add panel-level skeletons when chrome is up and only a panel is loading. |

## Where the system does something not communicated

- **Fund identity**: No persistent signal of whose system / what mandate (fund name, stage, geography).
- **Dashboard purpose**: Wordmark only; no one-line framing of what the system is doing ("Autonomous dealflow" or live pipeline summary).
- **Pipeline semantics**: Deal order, decision labels (Advance/Hold/Pass), escalation meaning, and one-line AI pipeline description are never explained in-app.
- **Autonomy vs human**: No copy stating what scouts/reviewer do autonomously vs where partner (human) judgment applies; no similar clarity in Settings next to agent toggles.

## Where a first-time viewer must infer

- That "SCOUTS RUNNING" means the system is working and deals will appear (when to expect first result could be explicit).
- That an empty Judgements feed is "live and waiting" rather than broken.
- What "signals" are and what triggers them (beyond "No signals detected").
- What a "cycle" is and when analytics/meta data will appear.
- That empty/zero budget and metrics are a clean starting state, not abandoned.
- How to read the pipeline (order, colours, decision badges, escalation dot).

## System copy (existing)

- WorkGrid empty: "SCOUTS RUNNING", "FIRST DISCOVERIES EXPECTED IN ~5 MINUTES".
- SystemIntelligence: "No signals detected", "No pending escalations", "No cycles completed yet", "No rejection data yet", "No pipeline data yet".
- Settings: section intros (e.g. "Scouts find companies, Reviewers score, Partners decide"), "Enable to enforce token and cost limits", etc.
- Status strip: "{n} companies · {n} decided", "Unreviewed X · Undecided Y · Watchlist Z", "{n} escalations".
- Memo: "Investment memo", "Investment judgment", "Overview", "Primary drivers", "Supporting analysis", "Decision".

## Gaps this pass addresses

1. Fund identity strip (config-driven) in spine or adjacent to wordmark.
2. Orientation subtitle under wordmark (dynamic where possible).
3. Deliberate, consistent empty states for WorkGrid, LiveIntelligenceFeed, SystemIntelligence (signals + analytics), Settings budget/metrics.
4. Collapsible pipeline legend (order, decision states, escalation, one-line pipeline).
5. Panel-level skeleton loaders for WorkGrid, SystemIntelligence, LiveIntelligenceFeed; global loader only for app boot; Settings loading = skeleton in chrome.
6. Autonomy/control micro-copy in SystemIntelligence and Settings (Pipeline).
7. Memo: judgment first (tinted card), primary vs supporting weight, decision anchored at bottom.
