-- Startups split — CONTRACT phase. Part 2 of 2. DO NOT APPLY until the app
-- code (supabase_storage.py) reads/writes startup_reviews AND populates the
-- promoted review_* columns at write time. Apply order: expand -> deploy code -> contract.
-- Best landed WITH the plain-Postgres migration, where it can be tested end-to-end.
-- See SUPABASE_SCHEMA_AUDIT.md.
--
-- Scope: move the 20 KB review_info (64% of the table) + agent_trace + financials
-- + memo OFF the hot startups row (now sourced from startup_reviews). scout_info /
-- partner_info are small (~2 KB / 1.5 KB) and STAY, so the scout/partner-derived
-- generated columns are untouched. Only the review_info-derived generated columns
-- must convert to plain (app-populated) columns, since review_info leaves the row.

begin;

-- 1. Promote review-derived projections to plain columns, backfilled from the
--    current generated values BEFORE review_info is dropped.
alter table public.startups
  add column if not exists review_score double precision,
  add column if not exists review_verdict text,
  add column if not exists review_consensus_verdict text,
  add column if not exists review_reviewer_disagreement boolean default false,
  add column if not exists review_reviewed_at text,
  add column if not exists review_short_summary text;

update public.startups set
  review_score                = list_score,
  review_verdict              = list_verdict,
  review_consensus_verdict    = list_consensus_verdict,
  review_reviewer_disagreement = coalesce(list_reviewer_disagreement, false),
  review_reviewed_at          = list_reviewed_at,
  review_short_summary        = short_summary;

-- 2. Drop the generated columns that depend on review_info.
alter table public.startups
  drop column if exists list_score,
  drop column if exists list_verdict,
  drop column if exists list_consensus_verdict,
  drop column if exists list_reviewer_disagreement,
  drop column if exists list_reviewed_at,
  drop column if exists short_summary;

-- 3. Drop the heavy payload columns (now canonical in startup_reviews).
alter table public.startups
  drop column if exists review_info,
  drop column if exists agent_trace,
  drop column if exists financials,
  drop column if exists investment_memo_markdown;

commit;

-- After this, the hot startups row holds: ids, scout_info (small), partner_info
-- (small), the scout/partner generated list_* columns, the promoted review_*
-- columns, lifecycle timestamps, and small jsonb (conviction_state, human_resolution).
-- review_info / agent_trace / financials / memo live only in startup_reviews,
-- joined in only on the detail/memo path.
