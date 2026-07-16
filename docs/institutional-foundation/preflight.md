# Institutional foundation preflight

Date: 2026-07-15

## Current-product regression gate

Command:

```bash
cd backend && pytest -q \
  tests/test_lookup_rerun.py \
  tests/test_company_resolver.py \
  tests/test_portfolio_layer.py \
  tests/test_job_schedule.py
```

Result: **32 passed, 1 skipped** in 4.11 seconds. The skipped case is the existing optional live-Supabase integration path. The run produced two upstream Supabase client deprecation warnings and no test failures.

This confirms the current regression coverage for:

- in-place re-review and memo regeneration;
- duplicate lookup returning the existing tenant-scoped company with an `already_in_deal_flow` outcome;
- portfolio signal/watchlist behaviour through the storage abstraction;
- atomic persistent schedule claims for Meta and Portfolio work.

## Required migration order

Apply these existing migrations in order before enabling the remediated workers:

1. `20260714192632_agent_job_schedules.sql`
2. `20260714192642_startups_normalized_name_unique.sql`
3. `20260714192902_optimize_agent_job_schedule_rls.sql`

Migration application is a target-environment deployment operation. Unit tests verify the SQL contract, but do not prove that a particular database has applied the migrations.

## Normalized-name duplicate preflight

Run this query before applying `20260714192642_startups_normalized_name_unique.sql`:

```sql
select
  user_id,
  lower(btrim(display_name)) as normalized_display_name,
  count(*) as duplicate_count,
  array_agg(startup_id order by created_at, startup_id) as startup_ids
from public.startups
where nullif(btrim(display_name), '') is not null
group by user_id, lower(btrim(display_name))
having count(*) > 1
order by duplicate_count desc, user_id, normalized_display_name;
```

Every returned group requires an operator decision. Do not automatically delete or merge tenant data. The migration deliberately aborts while duplicates remain.

## Dispatch compatibility

The current resolver and lookup tests verify that an existing-company result preserves the tenant-scoped startup ID and supports the remediated open-existing or in-place re-review path. Phase 2 will replace the normalized-name stopgap with canonical identity; Phase 0–1 does not reimplement it.
