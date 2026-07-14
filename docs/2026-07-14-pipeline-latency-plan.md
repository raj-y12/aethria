# Pipeline Latency — Where the Time Goes and How to Fix It

**Date:** 2026-07-14
**Symptom:** both the periodic scout→reviewer→partner pipeline and the dispatch (on-demand lookup) pipeline take too long per startup.
**Method:** traced the dispatch critical path through the code; every claim below is a verified code path, not a guess. Numbers marked ~ are estimates to be confirmed by Phase 0 instrumentation.

---

## The dispatch critical path (as implemented today)

```
POST /api/startups/lookup
  │ 1. queue wait          MAX_CONCURRENT_LOOKUPS = 2 (process-wide; tuned for Render 512MB)
  │ 2. engine build        builds 4 scouts + 3 reviewers + partner engine per lookup,
  │                        each constructor doing its own Supabase reads (settings, policy,
  │                        calibration, DealMemory) — the lookup uses ONE scout
  │ 3. company resolver    up to 2 phases × several Tavily queries — run SEQUENTIALLY
  │                        (retrieval_grounding.py:237-240 loops `for q in general_queries`)
  │                        …and the dispatch picker ALREADY resolved this exact input via
  │                        /lookup/resolve moments earlier; the worker re-resolves from scratch
  │ 4. scout stage         LLM call + its own retrieval pack + reference URL probes:
  │                        probe_url_status() is SEQUENTIAL, 4s timeout, up to 3 URLs/reference
  │                        (reference_verify.py:204, filter_references_by_url_probe)
  │ 5. persist → handoff   reviewer RE-READS the row we just wrote from Supabase; because
  │                        PostgREST can be briefly stale, there's a retry loop with
  │                        sleep(0.8s), sleep(1.6s) (pipeline_runner.py:790-805)
  │ 6. reviewer stage      gap retrieval (more sequential Tavily) → 3 persona LLM calls
  │                        (parallel — latency = slowest of 3) → full-row read + write
  │ 7. partner stage       rule-based (fast); LLM only on versioned edge cases;
  │                        another full-row read + write
  ▼
card ready
```

Rough wall-clock: with ~8–12 sequential Tavily calls at 1–3s each, ~2–4 LLM round trips on the
critical path, up to `3 × refs × 4s` of URL probes worst-case, and ~2.4s of handoff sleeps,
**60–120s per dispatch is exactly what this code produces.** The periodic pipeline has the same
per-startup cost plus throughput caps: the reviewer processes startups **sequentially inside the
batch** (3 parallel personas per startup, but one startup at a time), batch capped at 3–5/cycle,
cycle every 300s — a 15-deal backlog takes ~3–5 cycles (15–25 min) to drain.

---

## Phase 0 — Measure (half a day, do first)

`pipeline_stage_log` already emits STARTED/DONE per stage. Add stage-duration histograms to
`metrics.py` (resolver, scout_llm, reference_probes, gap_retrieval, reviewer_llm, partner,
persist) and log them per lookup. One day of real data confirms the ranking below before we
spend effort. (Karpathy rule: the estimates below are assumptions until this lands.)

## Phase 1 — Quick wins, no behavior change (days) — expect ~2× faster

1. **Parallelize retrieval queries in `retrieve_source_pack_merged`** (`utils/retrieval_grounding.py`).
   One function; the resolver, scout retrieval, and reviewer gap retrieval all flow through it.
   Run the general queries with `asyncio.gather`/small thread pool (concurrency 4), keep the
   recency-first quota logic by merging in a deterministic order after the fetches. Turns ~6–10
   serial searches into ~2 rounds. **Biggest single win in the codebase.**
2. **Parallelize reference URL probes** (`filter_references_by_url_probe`): probe all references'
   URLs concurrently (cap 8), drop the timeout 4s → 2s. Worst case goes from `N×3×4s` to ~2–4s flat.
3. **Stop re-resolving what the picker already resolved.** `run_named_lookup` already accepts a
   `resolution=` parameter — it's just never fed. Cache the `CompanyResolution` produced by
   `POST /api/startups/lookup/resolve` (keyed `user_id + normalized input`, ~5-min TTL) and pass
   it through the lookup queue payload. Removes the entire resolver stage (~10–30s) from the
   dispatch critical path whenever the user came through the picker — which is the normal flow.
4. **Kill the handoff re-read + sleeps.** For the lookup path, pass the in-memory `Startup` from
   the scout stage into `reviewer_engine.run_startup(...)` (new optional `startup=` param) instead
   of re-reading Supabase and sleeping around staleness. Same for reviewer → partner. Removes up
   to ~2.4s of sleeps, two full-row reads, and deletes the staleness failure mode outright.

## Phase 2 — Cheap structural (a week) — throughput + tail latency

5. **Slim engine construction for lookups.** Build only the scout the lookup uses (always
   `market_driven` today), make `DealMemory`/`CostController` lazy, and reuse the settings dict
   `pipeline_runner` already loaded instead of letting each constructor re-load it.
6. **Parallelize the reviewer batch in the periodic cycle.** The per-startup work is already
   isolated; wrap the loop body in `asyncio.gather` with a semaphore of 2–3 startups. Backlog
   drain rate triples without raising any cost cap (same number of LLM calls, sooner).
7. **Raise `MAX_CONCURRENT_LOOKUPS`** on the Oracle/Coolify box (the 2 was a Render-512MB
   number). 4–6 is safe with the per-cycle engine close discipline already in place.
8. **Skip reviewer gap retrieval when scout evidence is already rich** (e.g. ≥N verified
   `source_evidence` entries) — it exists to fill gaps, not to run unconditionally.

## Phase 3 — Perceived latency (the one users feel most)

9. **Fast-lane dispatch verdict.** Run ONE persona (DefaultReviewer) + partner immediately and
   publish the card with a *provisional* verdict, then let the other two personas + consensus +
   blend complete in the background and update the row (SSE nudge already makes the UI refresh,
   `pipeline_state` already models multi-step readiness, and the memo endpoint already serves
   partials). First verdict lands in roughly half the LLM time; final consensus replaces it a
   minute later, visibly labeled "consensus pending → consensus". No new frontend architecture —
   this is the existing progressive-memo pattern applied one stage earlier.
10. **Event-driven periodic pipeline** (review a startup the moment its scout row persists,
    rather than in the next batch sweep) — only worth it if cadence still feels slow after 1–2.
    It replaces the cycle model, so treat it as its own project, not a tweak.

---

## The main (periodic) pipeline — its own latency anatomy

Dispatch latency is *per-startup depth*; the main pipeline's problem is **cycle overhead ×
throughput caps × dead time between cycles**. A startup scouted in cycle N is usually reviewed
and decided in the same cycle **only if** the reviewer's batch cap (3–5) has room; otherwise it
waits 300s per cycle it's queued behind. The per-cycle anatomy:

```
_run_one_pipeline_cycle_inner (every AGENT_LOOP_INTERVAL_SECONDS = 300s per user)
  │ fixed overhead        settings (uncached) + storage + thesis triad + build 4 scouts,
  │                       3 reviewers, partner (each ctor does Supabase reads)
  │ bookkeeping           ~8 count queries per cycle (before/after per stage + runner totals)
  │ scout stage           4 personas in parallel (good) — but each discovery internally runs
  │                       the same SEQUENTIAL retrieval + SEQUENTIAL URL probes as dispatch
  │ reviewer stage        get_unreviewed lookahead = select("*") up to 500 FULL rows
  │                       (supabase_storage.py:1110), then startups processed ONE AT A TIME
  │                       (3 personas parallel per startup), capped at 3–5/cycle
  │ partner stage         get_undecided select("*") full rows incl. large review_info JSON;
  │                       sequential, mostly rule-based (fast)
  │ portfolio stage       ALL FOUR sub-stages forced every cycle (audit Bug 6) — execution
  │                       scan + signal Tavily checks + "daily" feedback metrics + health
  │ meta stage            MetaAgent runs EVERY cycle (audit Bug 5) — analyser reads, report row
  ▼
sleep(300) — fixed, even when unreviewed/undecided backlog remains
```

Two structural multipliers make this worse than it looks:

- **`MAX_CONCURRENT_PIPELINE_CYCLES = 1` is global, not per-user.** One user's bloated cycle
  (portfolio + meta overhead included) blocks *every other user's* cycle. With N active users,
  effective cycle latency is N × cycle duration.
- **The 300s sleep is unconditional.** A backlog of 15 unreviewed startups drains at 3–5/cycle
  → 3–5 cycles → 15–25 minutes of which most is sleeping, not working.

### Main-pipeline fixes (in addition to shared Phase 1 items)

M1. **Fix audit Bugs 5 & 6 — they are latency bugs too.** Gating MetaAgent to its daily interval
    and the portfolio feedback/signal/health stages to their intended intervals removes the
    largest *unnecessary* work from every 5-minute cycle. This directly shortens the global
    semaphore hold time for all users. (Same fix as the audit; counted once, paid twice.)
M2. **Drain mode instead of fixed sleep.** At cycle end, if `unreviewed > 0 or undecided > 0`,
    sleep 15–30s instead of 300s (the `wake_event` machinery in `api.py` already supports early
    wake — this is a timeout argument, not new architecture). Backlog drain goes from
    15–25 min to ~2–4 min with zero extra LLM spend per startup.
M3. **Parallelize the reviewer batch** (= Phase 2 item 6): startups concurrently with a
    semaphore of 2–3; personas are already parallel within each. This is the throughput fix;
    M2 is the dead-time fix; they compound.
M4. **Raise `MAX_CONCURRENT_PIPELINE_CYCLES`** on the Oracle box (2–3), keeping the per-user
    lock so one user never runs two cycles. Removes the cross-user serialization penalty.
M5. **Trim stage fetches.** `get_unreviewed` lookahead pulls up to 500 full rows with
    `select("*")` per cycle; it only needs scout columns + confidence for ordering and the
    threshold skip. `get_undecided` genuinely needs `review_info`, but not
    `investment_memo_markdown`/`agent_trace`. Cheap egress + parse win, matters on small
    instances (this is the same class of fix as the list-projection work already done for the
    API layer — apply it to the engines).
M6. **Cut the bookkeeping counts.** The runner and each engine independently count
    unreviewed/undecided before and after (~8 queries/cycle). The stage functions already
    return counts; log those instead and keep at most one count pair per cycle.

### Expected outcome (main pipeline)

M1+M2 alone: a fresh discovery goes from "decided within 5–25 min depending on backlog" to
**"decided within one working cycle, cycles back-to-back while backlog exists."** With M3+M4,
multi-user deployments stop serializing behind each other's overhead. Shared Phase 1 items
(parallel retrieval + probes) shrink the scout stage inside every cycle the same way they
shrink dispatch.

---

## What NOT to do

- **Don't swap models or cut personas as the first move.** The 3-persona consensus is the
  product's credibility; the audit shows the time is mostly in *sequential I/O we control*
  (searches, probes, re-reads), not in LLM inference.
- **Don't remove reference verification or the resolver** to save time — they're the moat against
  hallucinated companies. Make them concurrent, not absent.
- **Don't raise scout wave counts** to feel faster; that increases backlog pressure on the
  reviewer, which is the throughput bottleneck (fix 6 first).

## Expected outcome

Phase 1 alone: dispatch ~60–120s → **~30–50s**. With Phase 2 + fast lane: **first verdict in
~15–30s**, consensus complete in the background; periodic backlog drain ~3× faster at identical
LLM spend. All numbers to be validated against Phase 0 histograms.
