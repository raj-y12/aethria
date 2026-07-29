# Full Codebase Audit — Feature Validation, Bugs, and Redesign Candidates

**Date:** 2026-07-14
**Scope:** Every documented feature, backend (`backend/`) and frontend (`app-front-end/src/`), validated against its stated intent (CLAUDE.md, docstrings, versioned rules). Both test suites pass (backend: 445 passed / 4 skipped; frontend: 192 passed) — every bug below lives in an untested path.

---

## Part 1 — Feature validation matrix

Verdicts: ✅ implemented as intended · ⚠️ implemented but with defects/drift · ❌ misimplemented vs stated design.

| Feature (stated intent) | Verdict | Evidence |
|---|---|---|
| Multi-tenancy: explicit `user_id` on every storage/engine path | ✅ | `require_user_id()` enforced in ScoutEngine/ReviewerEngine/PartnerEngine/MetaAgent constructors; all Supabase queries filter `user_id`. No implicit tenant found. |
| Fund thesis hard gate on periodic pipeline | ✅ | `pipeline_runner.py:354-375` skips the cycle on missing/incomplete thesis; bootstrap is idempotent with concurrent-request re-checks (`fund_thesis.py:541-677`). |
| Lookup is mandate-aware but never thesis-blocked | ✅ | `pipeline_runner.py:685-698` — matches the documented design and the project memory. |
| Scout: 4 personas, meta-weighted selection, backpressure, ramp waves | ✅ | `scout/engine.py` — weights from `meta.reweighter`, backpressure at 10 unreviewed, ramp to 2 waves. |
| Reviewer: 3 personas in parallel, consensus, deterministic structured scoring | ✅ | `reviewer/engine.py` — blend + resolution + confidence-adjusted score + scoring trail. Sound. |
| Partner: rule-based default, LLM only for versioned edge-case triggers | ✅ | `partner/decision.py` — thresholds from `partner_rules` + fund_config with ordering-invariant clamps; mandate-fit gate holds strong-but-off-thesis deals for IC exception. Well built. |
| Reference validation "mandatory; pruned" | ⚠️ | In-line verification at scout time is real (`scout/base.py` + `utils/reference_verify.py`). But the prune stage `remove_startups_without_references()` is only called from `run_system.py` (dev CLI) — it never runs in the production `run_one_pipeline_cycle`. Docs overstate the behavior. |
| Portfolio: execution / signals / feedback / health on distinct intervals | ❌ | Interval design is defeated: `pipeline_runner.py:484-487` backdates all `last_*` stamps a day, so all four stages run every cycle (~5 min), including the "daily" feedback loop. See Bug 6. |
| MetaAgent runs on a daily interval (CLAUDE.md constraint #6) | ❌ | `run_one_pipeline_cycle` invokes `meta_agent.run_cycle()` every cycle; `MetaAgent.interval` is only used to print `next_cycle_at`. See Bug 5. |
| Row-level Supabase upserts, no delete+rewrite | ✅ | Targeted column updates preserve TOAST pointers (`supabase_storage.py:_update_startup_columns`); `replace_all` is upsert-first/prune-after. Schema-drift detection at startup is a nice touch. |
| SSE push + poll backstop | ✅ | `event_bus.py` (bounded queues, drop-oldest, optional Postgres backplane, prod fail-closed) and `useStartupsStream` (healthy = hello frame parsed, not HTTP 200) are genuinely well designed. |
| Auth: Clerk RS256 via JWKS, fail-closed | ✅ | `auth_clerk.py`; JWKS fetch off the event loop; issuer/audience verified when configured. |
| Warm start (instant login paint) | ✅ | `warmStart.ts` — per-user snapshot, real `dataUpdatedAt`, idle-only invalidate. But it interacts badly with Settings (see Part 3, item 7). |
| Cost budgets respected in engines | ✅ | `check_budget` gates in scout/reviewer/partner; usage recorded per stage. |
| Per-user cost/settings via Supabase, no global config | ✅ | `load_settings(user_id)` everywhere; `agents_status` best-effort. |

---

## Part 2 — Confirmed bugs (ranked)

### Bug 1 (P1) — Post-hoc re-review crashes at memo regeneration
`POST /api/startups/{id}/rerun` → `pipeline_runner.py:853-858` calls `MemoGenerator().generate_memo(updated_startup, ...)` **without `for_display=True`**. The `for_display=False` branch (`memo_generator.py:414-427`) reads `startup.partner_info.decision`, `.conviction_level`, and `.rationale` — none of which exist on `PartnerInfo` (verified at runtime: `hasattr(p, 'decision') == False`; the model has `recommendation` / `confidence` / `decision_rationale`). Every re-review that reaches memo regeneration raises `AttributeError`, the lookup is marked failed, and the regenerated memo is never persisted.
**Fix:** pass `for_display=True` (the stored `investment_memo_markdown` *is* the display memo — `api.py`'s own fallback path uses `for_display=True`), and separately repair or delete the legacy-field internal-memo branch.

### Bug 2 (P1) — Duplicate-company lookup reports a phantom failure
`SupabaseStartupsStorage.add_startup` (`supabase_storage.py:762-780`): when a row with the same `display_name` exists, it skips the insert but returns the **new** UUID. The scout reports success with that id, the reviewer then can't find the row, retries 3×, and the user sees *"Lookup found the company, but analyst review could not complete after retrying"* — for the mundane case of looking up a company already in their deal flow.
**Fix:** return the existing row's `startup_id` (re-review it in place), or surface an explicit "already in your deal flow" outcome via `last_lookup_outcome`.

### Bug 3 (P2) — Watchlist decay reads local files in Supabase mode
`portfolio/engine.py:285` calls `portfolio_store._read_file(portfolio_store.files["signals"])` — the raw JSON-file fallback — even when signals live in the `portfolio_signals` Supabase table. `has_signals` is therefore always `False` in production: every watchlist entry older than 60 days is escalated to human review regardless of live signals, and 30–60-day entries get `stale_warning` records appended repeatedly (once per cycle, since the stamps are backdated — see Bug 6).
**Fix:** add/use a store method that respects the Supabase backend, and de-duplicate the stale-warning write.

### Bug 4 (P2) — `get_startups_with_decision(decision=...)` filter can never work
`supabase_storage.py:1192` and `utils/storage.py:373` filter with `s.partner_info.decision`, which raises `AttributeError` on the Pydantic model. Currently latent (the only caller, `portfolio/engine.py:256`, passes no `decision`), but it's a landmine — same root cause as Bug 1 (legacy `decision` vs `recommendation` duality).

### Bug 5 (P2) — MetaAgent runs every ~5 minutes, not daily
CLAUDE.md constraint #6: "MetaAgent runs on a daily interval." Reality: `run_one_pipeline_cycle` calls `meta_agent.run_cycle()` unconditionally each cycle; `META_AGENT_INTERVAL_SECONDS` never gates execution. Effects: `meta_cycle_counters` inflates and a `meta_reports` row is appended every cycle; once data sufficiency is reached (≥20 reviews, ≥10 decisions), prompt mutation / reweighting / calibration can churn every 5 minutes instead of daily.
**Fix:** persist `last_meta_run_at` (doc store) and skip unless `interval` has elapsed.

### Bug 6 (P2) — PortfolioEngine's interval scheduling is dead code
`pipeline_runner.py:484-487` backdates `last_execution/last_signal/last_feedback/last_health` by a day on every cycle, forcing all four portfolio stages (including the "daily" feedback loop and hourly signal scan) to run every ~5 minutes. The engine is rebuilt per cycle, so its in-memory stamps can never work.
**Fix:** either persist last-run timestamps per user, or delete the interval machinery and be explicit that all stages run per cycle (then rate the stages accordingly).

### Bug 7 (P3) — Cancel-set clear un-cancels in-flight lookups
`api.py:181-184`: when `_cancelled_lookup_ids` reaches 1000 entries it is **cleared entirely**, silently un-cancelling any queued/running lookup that had just been cancelled. Use ordered eviction (dict-as-FIFO/LRU) instead of `clear()`.

### Bug 8 (P3) — `toggle_agents(enabled=true)` can report "running" with nothing running
`api.py:2196-2216`: enabling writes `agents_status="running"` but deliberately doesn't enable any stage toggle; if all three are off, `_user_agent_loop` exits on its first check while settings still say "running". Either flip at least the saved stage toggles on, or don't stamp "running" until the loop confirms.

---

## Part 3 — Design drift / redesign candidates

1. **Kill the YES/NO/MAYBE ↔ INVEST/PASS/MONITOR duality.** It has now caused two real bugs (Bugs 1 & 4) and permeates storage (`partner_decision` column), portfolio records, memo_generator, and `utils/partner_codes`. Recommendation: `recommendation` is the single canonical enum on `PartnerInfo`; keep legacy codes only in `human_resolution` (a genuinely different concept — human ruling) and at the DB column boundary via one adapter.

2. **Settings fund-thesis staleness** — already root-caused in `docs/2026-07-14-settings-fund-thesis-stale-diagnosis.md`. Implement its option 1 (reconcile-on-fresh-data when no unsaved edits) or 2 (`refetchOnMount: 'always'` for the Settings observer).

3. **Dual source of truth for the mandate** (same doc, root cause B): `settings.fund_config` ↔ `fund_thesis` tables sync one-way. `POST /api/fund-thesis/versions` and `PATCH /api/fund-thesis/active` have **no frontend callers** — either delete them or make them write the derived mandate back into `settings.fund_config`.

4. **Delete the standalone `run_forever()`/`main()` blocks in all four engines** (`scout/engine.py:466-563`, `reviewer/engine.py:1040-1143`, `partner/engine.py:472-553`, `portfolio/engine.py:354-408`). The per-user loop in `api.py` is the real orchestrator; these are unmaintained second orchestrators with their own (diverging) backpressure logic. `run_system.py` can keep a thin cycle-loop wrapper if the CLI is still wanted.

5. **ReviewerEngine `run_cycle` vs `run_startup` duplicate ~150 lines** of the persona-fanout → blend → resolution → thesis-alignment → persist sequence. Extract one `_review_one(startup, ...)` used by both; same (smaller) duplication in PartnerEngine.

6. **`api.py` is still 2,664 lines.** The router split (meta, fund_thesis, analytics) is working — continue it: `routers/startups.py` (list/detail/memo/acknowledge), `routers/lookup.py` (lookup/resolve/rerun/cancel), `routers/agents.py` (trigger/toggle/status + the loop registry), `routers/admin.py`.

7. **Queue-reason strings are computed in two places** that can drift: `_queue_reasons_for_startup` (storage, persisted) and `_default_queue_reason`/`_default_priority_reason` (api.py, fallback). Move the fallback to import the storage version.

8. **Reference-prune stage**: either call `remove_startups_without_references()` from the pipeline cycle (its origin-type and resolution-status guards make it safe) or delete it and amend CLAUDE.md — scout-time verification is the actual gate today.

9. **`resolve_lookup_candidates`** uses deprecated `asyncio.get_event_loop()` + default executor; use `asyncio.to_thread` like every other blocking call in the file. Same pattern in `scout/engine.py:329`.

10. **Planned architecture work remains right**: the plain-Postgres refactor (replacing supabase-py + PostgREST retries + the `_is_missing_*_error` string-matching fallbacks with real migrations/transactions) would delete a whole class of defensive code in `supabase_storage.py` — roughly 300 lines of column-fallback machinery exists only because migrations can drift. The startup schema-drift probe is a good stopgap; the refactor is the fix.

---

## Part 4 — Things worth keeping exactly as they are

Called out so nobody "fixes" them: the SSE hello-nudge race closure (`api.py:_sse_event_source`), event-bus drop-oldest bounded queues, the 503-instead-of-full-fallback on list projection failure (deliberate egress protection), `replace_all`'s upsert-first/prune-after ordering, the tenant cache-clear `useLayoutEffect` on account switch in `App.tsx`, warm-start preserving real `dataUpdatedAt`, the mandate-fit gate separating company quality from fund fit, and `_json_within_budget`'s always-valid-JSON prompt truncation.

## Part 5 — Feature suggestions (add)

- **"Already in deal flow" dispatch outcome** (falls out of Bug 2's fix): dispatching a known company should offer *open existing memo* or *re-review with new context*.
- **Meta-agent report surface**: once Bug 5 is fixed, the daily report (`no_action_reasons`, mutations, calibrations) is exactly the kind of content the Fund workspace's intelligence panel wants; today it's buried in a table nobody reads.
- **Escalation queue aging**: `unresolved_at` is persisted but nothing surfaces "held 5 days without ruling"; a sort/badge on the flow docket would close the loop the partner engine starts.
- **Thesis-version stamped on lookups**: lookups store `fund_thesis_version_id` when reviewed; expose "evaluated under thesis vN" in the memo header so old memos are legible after a mandate change (the data is already there).

## Part 6 — Remove / retire

- Engines' `run_forever`/`main` blocks (Part 3.4).
- `POST /api/fund-thesis/versions` + `PATCH /api/fund-thesis/active` (or close the write-back loop) (Part 3.3).
- `utils/storage.py` file backend once the Postgres refactor lands — today it's a second full storage implementation kept in sync by hand.
- `_legacy_get_startups_with_decision` (broken anyway, Bug 4).
- `SCOUT_RAMP_*`/`REVIEWER_RAMP_*` env sprawl could collapse into `agent_config` settings — env vars for per-user-tunable behavior fight the settings system.

---

## Remediation record

The `codex/audit-remediation` work uses this audit as its baseline.

| Item | Remediation |
|---|---|
| Bug 1 | Rerun memo persistence explicitly generates the display memo; the internal memo and summary now use `recommendation`, `confidence`, and `decision_rationale`. |
| Bug 2 | Both storage backends return the existing tenant-scoped startup ID for duplicate names; ScoutEngine propagates and persists that ID with an `already_in_deal_flow` outcome that Dispatch can open. Migration `20260714192642_startups_normalized_name_unique.sql` adds a normalized tenant/name unique index to close concurrent insert races. |
| Bug 3 | The original claim that `_read_file()` always read local JSON was not accurate—it already dispatched to Supabase. PortfolioEngine now uses a public `get_all_signals()` boundary, and stale warning updates are idempotent. |
| Bug 4 | Decision filters normalize both legacy and canonical input, then compare `PartnerInfo.recommendation`. |
| Bugs 5–6 | Meta and portfolio stages use atomic per-user PostgreSQL schedule claims. Migration `20260714192632_agent_job_schedules.sql` and its verification follow-ups are required before deployment. Timestamp backdating was removed. |
| Bug 7 | Cancellation state is insertion-ordered and evicts only the oldest key at capacity. |
| Bug 8 | Enabling the global loop with every stage disabled returns `409`, persists `stopped`, and does not start a loop. |
| Drift 8 | Production cycles invoke reference pruning after scout and before reviewer. |
| Drift 9 | The audited default-executor call sites use `asyncio.to_thread`. |

The API router split, standalone-loop retirement, reviewer deduplication, and direct-Postgres migration remain separate architectural projects rather than being bundled into the runtime correctness change.

### Deployment preflight

Apply the `20260714192632` through `20260714192902` migrations in order before starting the remediated workers. Before applying `20260714192642_startups_normalized_name_unique.sql`, run its normalized-name duplicate query and deliberately reconcile any rows it reports. The migration aborts instead of guessing which tenant data to merge or delete.
