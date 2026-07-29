# Codebase Audit Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Correct every confirmed runtime defect in the 2026-07-14 codebase audit and cover each corrected path with regression tests.

**Architecture:** Canonicalize decisions at model boundaries, return explicit duplicate-add results, persist user-scoped schedule timestamps, and move portfolio behavior behind backend-aware store methods. Keep broad API and database-client rewrites out of this correctness change.

**Tech Stack:** Python 3, FastAPI, Pydantic, asyncio, Supabase/PostgREST, pytest.

## Global Constraints

- Every engine, storage operation, and persisted schedule uses an explicit `user_id`.
- Production pipeline execution continues to require Supabase and an OpenAI API key.
- Partner decision thresholds remain in versioned JSON and are not changed here.
- Existing uncommitted user changes are preserved.
- Production code is changed only after its regression test fails for the expected reason.

---

### Task 1: Canonical partner decision and memo behavior

**Files:**
- Modify: `backend/memo_generator.py`
- Modify: `backend/pipeline_runner.py`
- Modify: `backend/supabase_storage.py`
- Modify: `backend/utils/storage.py`
- Test: `backend/tests/test_memo_generator.py`
- Test: `backend/tests/test_on_demand_lookup_independent.py`
- Test: `backend/tests/test_supabase_storage.py`

**Interfaces:**
- Consumes: `PartnerInfo.recommendation`, `decision_rationale`, `confidence`, `next_action`.
- Produces: valid internal/display memo Markdown and recommendation-aware `get_startups_with_decision()` behavior.

- [x] Add tests proving a valid current `PartnerInfo` can generate both memo variants and summaries.
- [x] Run the focused tests and confirm failures reference removed legacy attributes.
- [x] Render canonical recommendation/confidence/rationale and explicitly use display mode for persisted rerun memos.
- [x] Add tests for canonical and legacy decision filter inputs.
- [x] Normalize filters through `utils.partner_codes` and remove production reads of `partner_info.decision`.
- [x] Run the focused tests until green.

### Task 2: Duplicate lookup identity and explicit outcome

**Files:**
- Modify: `backend/supabase_storage.py`
- Modify: `backend/utils/storage.py`
- Modify: `backend/pipeline_runner.py`
- Test: `backend/tests/test_on_demand_lookup_independent.py`
- Test: `backend/tests/test_supabase_storage.py`

**Interfaces:**
- Produces: the canonical persisted `startup_id`; ScoutEngine derives whether it already existed by comparing it with the newly scouted UUID.
- Consumes: lookup outcome persistence in `pipeline_runner.py`.

- [x] Add a failing storage test proving duplicate display names return the existing tenant-scoped ID.
- [x] Add a failing lookup test proving the runner does not review a phantom UUID.
- [x] Return the canonical existing ID without breaking the storage method's string return contract.
- [x] Record `already_in_deal_flow` and use the existing startup ID.
- [x] Run storage and lookup tests until green.

### Task 3: Durable MetaAgent and portfolio scheduling

**Files:**
- Create: `backend/utils/job_schedule.py`
- Modify: `backend/meta/agent.py`
- Modify: `backend/portfolio/engine.py`
- Modify: `backend/pipeline_runner.py`
- Test: `backend/tests/test_job_schedule.py`
- Test: `backend/tests/test_meta_agent.py`
- Test: `backend/tests/test_portfolio_layer.py`

**Interfaces:**
- Produces: `claim_due_jobs(user_id: str, intervals: Mapping[str, int], now: datetime | None = None) -> Set[str]`.
- Consumes: the service-role-only `claim_due_agent_jobs` PostgreSQL function.

- [x] Add tests for first claim, not-due claim, elapsed claim, and tenant isolation.
- [x] Add MetaAgent and reconstructed-PortfolioEngine tests that fail under the current in-memory scheduling.
- [x] Implement atomic user-scoped due claims through a service-role-only PostgreSQL RPC.
- [x] Gate MetaAgent and each portfolio stage through durable claims; remove timestamp backdating.
- [x] Run scheduling, MetaAgent, and portfolio tests until green.

### Task 4: Portfolio signal storage and idempotent stale warnings

**Files:**
- Modify: `backend/portfolio/store.py`
- Modify: `backend/portfolio/engine.py`
- Test: `backend/tests/test_portfolio_layer.py`
- Test: `backend/tests/test_portfolio_supabase.py`

**Interfaces:**
- Produces: backend-aware signal startup IDs and an update-in-place watchlist operation.
- Consumes: PortfolioEngine watchlist review.

- [x] Add failing tests using the Supabase-backed store and repeated stale-review cycles.
- [x] Implement storage methods that select signals and update an existing watchlist entry.
- [x] Replace direct `_read_file` and `_append_record` calls in PortfolioEngine.
- [x] Run portfolio tests until green.

### Task 5: Cancellation eviction and truthful agent enablement

**Files:**
- Modify: `backend/api.py`
- Test: `backend/tests/test_security_api.py`
- Test: `backend/tests/test_agent_loops.py`

**Interfaces:**
- Produces: ordered bounded cancellation membership and an enable endpoint that requires an enabled stage.

- [x] Add a failing test proving capacity eviction preserves newer cancellation keys.
- [x] Add a failing test proving enablement with all stages off returns a validation response and persists stopped state.
- [x] Replace clear-all cancellation behavior with oldest-only eviction.
- [x] Validate stage toggles before marking or starting the loop.
- [x] Run API and loop tests until green.

### Task 6: Reference enforcement and async cleanup

**Files:**
- Modify: `backend/pipeline_runner.py`
- Modify: `backend/scout/engine.py`
- Modify: the lookup-candidate API module containing `resolve_lookup_candidates`
- Test: `backend/tests/test_pipeline_runner.py`
- Test: relevant scout and API tests.

**Interfaces:**
- Consumes: existing `remove_startups_without_references()` guards.
- Produces: production-cycle pruning and `asyncio.to_thread` dispatch for blocking work.

- [x] Add a failing pipeline test proving pruning occurs after scouting and before review.
- [x] Invoke pruning through `asyncio.to_thread` and report its count.
- [x] Replace both audited `get_event_loop().run_in_executor` usages with `asyncio.to_thread`.
- [x] Run focused pipeline, scout, and API tests until green.

### Task 7: Verification and baseline audit

**Files:**
- Modify: `docs/2026-07-14-full-codebase-audit.md` only if status annotations are needed.

**Interfaces:**
- Consumes: all remediation tasks.
- Produces: fresh verification evidence for every baseline bug and selected drift item.

- [x] Run every focused regression test added above.
- [x] Run the complete backend test suite.
- [x] Search production code for removed `PartnerInfo` legacy attribute reads.
- [x] Inspect the final diff for unrelated or accidental edits.
- [x] Re-read every audit item and record fixed, intentionally deferred, or already-correct status.
