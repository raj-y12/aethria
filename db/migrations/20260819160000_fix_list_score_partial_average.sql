-- Fix list_score generated column: exclude unscored dimensions from the
-- average instead of treating them as a literal 0/10 failing score.
--
-- The original formula (20260811000018_startups_read_contract.sql) summed
-- COALESCE(dimension, 0.0) across market/product/technical/execution but
-- always divided by a fixed 4. A startup scored on only technical+execution
-- (the common case for partial-evidence reviews -- e.g. a lookup blocked by
-- missing evidence) got two phantom zeros averaged in: technical=4.31,
-- execution=5.56, market/product unscored produced (4.31+5.56+0+0)/4 = 2.47
-- (list_score 25 on the docket's 0-100 scale) instead of the true partial
-- average (4.31+5.56)/2 = 4.94 (score 49) -- which is what every other
-- scoring path (computeConfiguredScore, canonical evaluation criteria)
-- already computes by excluding unscored dimensions. This divergence showed
-- up as the docket row / dispatch snapshot score disagreeing with the memo.
--
-- Generated column expressions cannot be altered in place; drop and re-add.
alter table public.startups drop column if exists list_score;
alter table public.startups add column list_score double precision generated always as (
  case when review_info is null then null else
    case
      when (
        (case when (review_info ->> 'market_score') is not null then 1 else 0 end)
        + (case when (review_info ->> 'product_score') is not null then 1 else 0 end)
        + (case when (review_info ->> 'technical_score') is not null then 1 else 0 end)
        + (case when (review_info ->> 'execution_score') is not null then 1 else 0 end)
      ) = 0
      then null
      else (
        coalesce((review_info ->> 'market_score')::double precision, 0.0)
        + coalesce((review_info ->> 'product_score')::double precision, 0.0)
        + coalesce((review_info ->> 'technical_score')::double precision, 0.0)
        + coalesce((review_info ->> 'execution_score')::double precision, 0.0)
      ) / (
        (case when (review_info ->> 'market_score') is not null then 1 else 0 end)
        + (case when (review_info ->> 'product_score') is not null then 1 else 0 end)
        + (case when (review_info ->> 'technical_score') is not null then 1 else 0 end)
        + (case when (review_info ->> 'execution_score') is not null then 1 else 0 end)
      )
    end
  end
) stored;
