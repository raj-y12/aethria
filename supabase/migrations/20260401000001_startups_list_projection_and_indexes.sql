-- =============================================================================
-- Startups: list projection columns (generated), pagination index, RLS unchanged
-- =============================================================================
-- Enables GET /api/startups to select thin columns only (lower egress).
-- Generated columns stay in sync with scout_info / review_info / partner_info JSONB.
-- =============================================================================

-- Thin fields for grid / polling (no full scout blob in list queries)
alter table public.startups
  add column if not exists display_name text
    generated always as (nullif(trim(scout_info->>'name'), '')) stored;

alter table public.startups
  add column if not exists list_one_line text
    generated always as (nullif(trim(scout_info->>'one_line'), '')) stored;

alter table public.startups
  add column if not exists list_sector text
    generated always as (nullif(trim(scout_info->>'sector'), '')) stored;

alter table public.startups
  add column if not exists list_scout_type text
    generated always as (nullif(trim(scout_info->>'scout_type'), '')) stored;

alter table public.startups
  add column if not exists list_origin_type text
    generated always as (nullif(trim(scout_info->>'origin_type'), '')) stored;

alter table public.startups
  add column if not exists list_lookup_query text
    generated always as (nullif(trim(scout_info->>'lookup_query'), '')) stored;

alter table public.startups
  add column if not exists list_lookup_website text
    generated always as (nullif(trim(scout_info->>'lookup_website'), '')) stored;

alter table public.startups
  add column if not exists list_confidence double precision
    generated always as (
      coalesce(
        case
          when scout_info ? 'confidence_score'
               and nullif(trim(scout_info->>'confidence_score'), '') is not null
            then (scout_info->>'confidence_score')::double precision
          else null
        end,
        0.5::double precision
      )
    ) stored;

-- Average of four core scores when review exists
alter table public.startups
  add column if not exists list_score double precision
    generated always as (
      case
        when review_info is null then null
        else
          (
            coalesce((review_info->>'market_score')::double precision, 0.0)
            + coalesce((review_info->>'product_score')::double precision, 0.0)
            + coalesce((review_info->>'technical_score')::double precision, 0.0)
            + coalesce((review_info->>'execution_score')::double precision, 0.0)
          ) / 4.0
      end
    ) stored;

alter table public.startups
  add column if not exists list_verdict text
    generated always as (nullif(trim(review_info->>'verdict'), '')) stored;

alter table public.startups
  add column if not exists list_consensus_verdict text
    generated always as (nullif(trim(review_info->>'consensus_verdict'), '')) stored;

alter table public.startups
  add column if not exists list_reviewed_at text
    generated always as (nullif(trim(review_info->>'reviewed_at'), '')) stored;

alter table public.startups
  add column if not exists list_partnered_at text
    generated always as (nullif(trim(partner_info->>'partnered_at'), '')) stored;

alter table public.startups
  add column if not exists short_summary text
    generated always as (
      left(coalesce(nullif(trim(review_info->>'overall_summary'), ''), ''), 400)
    ) stored;

alter table public.startups
  add column if not exists list_reviewer_disagreement boolean
    generated always as (
      case
        when review_info is null then false
        when (review_info->'reviewer_disagreement') = 'true'::jsonb then true
        when lower(trim(review_info->>'reviewer_disagreement')) in ('true', '1', 'yes') then true
        else false
      end
    ) stored;

alter table public.startups
  add column if not exists partner_decision text
    generated always as (nullif(trim(partner_info->>'decision'), '')) stored;

alter table public.startups
  add column if not exists partner_human_review_required boolean
    generated always as (
      case
        when partner_info is null then false
        when (partner_info->'human_review_required') = 'true'::jsonb then true
        when lower(trim(partner_info->>'human_review_required')) in ('true', '1', 'yes') then true
        else false
      end
    ) stored;

create index if not exists startups_user_updated_at_desc_idx
  on public.startups (user_id, updated_at desc, startup_id desc);

create index if not exists startups_user_unreviewed_idx
  on public.startups (user_id)
  where review_info is null;

create index if not exists startups_user_undecided_idx
  on public.startups (user_id)
  where review_info is not null and partner_info is null;

create index if not exists startups_user_escalation_idx
  on public.startups (user_id)
  where partner_human_review_required = true;
