-- Startups split — EXPAND phase (additive, non-breaking). Part 1 of 2.
-- Pairs with 20260613000003_startups_split_contract.sql, which must run ONLY
-- after the application code reads/writes the new shape (expand → deploy → contract).
-- See SUPABASE_SCHEMA_AUDIT.md "startups split".
--
-- Goal: move the heavy JSONB (review_info ~20 KB/row, scout_info, partner_info,
-- agent_trace, financials, memo) off the hot `startups` row into a child table
-- read only on the detail/memo path. Hot row shrinks 29 KB -> ~1-2 KB.
--
-- This phase is safe to apply at any time: it only ADDS a table and backfills.
-- Existing columns and code keep working untouched.

create table if not exists public.startup_reviews (
  user_id     text not null,
  startup_id  text not null,
  scout_info  jsonb,
  review_info jsonb,
  partner_info jsonb,
  agent_trace jsonb,
  financials  jsonb,
  investment_memo_markdown text,
  updated_at  timestamptz not null default now(),
  primary key (user_id, startup_id)
);

alter table public.startup_reviews enable row level security;
-- Service-role only (same posture as startups); no anon/auth policies by design.

-- Backfill from the current startups table.
insert into public.startup_reviews
  (user_id, startup_id, scout_info, review_info, partner_info, agent_trace,
   financials, investment_memo_markdown, updated_at)
select user_id, startup_id, scout_info, review_info, partner_info, agent_trace,
       financials, investment_memo_markdown, coalesce(updated_at, now())
from public.startups
on conflict (user_id, startup_id) do update set
  scout_info  = excluded.scout_info,
  review_info = excluded.review_info,
  partner_info = excluded.partner_info,
  agent_trace = excluded.agent_trace,
  financials  = excluded.financials,
  investment_memo_markdown = excluded.investment_memo_markdown,
  updated_at  = excluded.updated_at;
