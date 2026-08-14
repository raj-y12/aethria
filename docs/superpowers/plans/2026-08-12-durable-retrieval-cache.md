# Durable Retrieval Persistence and Shared Cache Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Avoid repeat external retrieval calls while preserving tenant boundaries, freshness, provenance, and historical source versions.

**Architecture:** A provider-neutral PostgreSQL repository stores query cache entries, retrieval observations, and immutable source-content versions. The existing synchronous retrieval boundary consults one configured shared cache and persists successful provider results; canonical evidence remains a separate authority.

**Tech Stack:** Python, asyncpg, PostgreSQL migrations, Prometheus, pytest.

## Global Constraints

- Standard PostgreSQL is the persistence contract; no new Supabase-specific dependencies.
- Every storage operation receives an explicit `user_id` and uses `require_user_id()`.
- Public/private content remains tenant-scoped in this slice.
- Do not add pgvector, embeddings, people tables, contradiction gates, CRM work, frontend changes, or production migration work.

### Task 1: Cache schema and repository

**Files:**
- Create: `backend/retrieval_cache/repository.py`
- Create: `backend/retrieval_cache/__init__.py`
- Create: `supabase/migrations/20260812000001_durable_retrieval_cache.sql`
- Test: `backend/tests/retrieval_cache/test_repository.py`

- [ ] Add tenant-scoped cache entries, immutable content versions, and retrieval observations with indexes, RLS, and provider metadata JSONB.
- [ ] Add repository methods for fresh lookup, successful persistence, failed-attempt persistence, and diagnostics reads.
- [ ] Deduplicate exact content by `(user_id, content_hash, access_class)` while retaining changed URL versions.
- [ ] Add focused repository contract tests using the existing migration/test conventions.

### Task 2: Retrieval-boundary integration

**Files:**
- Modify: `backend/utils/retrieval_grounding.py`
- Modify: `backend/utils/search_providers.py`
- Modify: `backend/env_config.py`
- Modify: `.env.example`
- Test: `backend/tests/test_retrieval_cache.py`

- [ ] Add normalized query identity and category freshness policies.
- [ ] Consult the shared cache before provider calls and persist only usable successes; record failures without making them reusable.
- [ ] Serialize cache access safely for concurrent duplicate requests and preserve existing provider fallback behavior.
- [ ] Keep cache persistence optional when no PostgreSQL repository is configured so existing local/test seams remain valid.

### Task 3: Application wiring and diagnostics

**Files:**
- Modify: `backend/api.py`
- Modify: `backend/run_system.py`
- Modify: `backend/metrics.py`
- Test: `backend/tests/test_retrieval_cache_wiring.py`

- [ ] Configure the shared cache from the existing PostgreSQL pool at service startup and clear it during shutdown.
- [ ] Expose cache hit, miss, stale refresh, provider-call-avoided, and duplicate-suppressed metrics.
- [ ] Verify company resolver, founder resolver, Scout, and Reviewer gap retrieval reach the same boundary through their existing call paths.

### Task 4: Verification

- [ ] Run focused retrieval/cache tests and migration contract tests.
- [ ] Run the full backend pytest suite.
- [ ] Report changed files, migration, identity/freshness/version semantics, consumers, diagnostics, and actual test output.
