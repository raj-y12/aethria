-- Provider-neutral canonical startup read contract.
-- Generated list columns are intentionally read-only; runtime writes must target
-- their source columns and let PostgreSQL derive these values.

create table if not exists public.startups (
  id uuid primary key default gen_random_uuid(),
  user_id text not null,
  startup_id text not null,
  scout_info jsonb not null,
  review_info jsonb,
  partner_info jsonb,
  financials jsonb not null,
  version integer not null default 1,
  human_resolution jsonb,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now()),
  investment_memo_markdown text,
  conviction_state jsonb,
  unresolved_at timestamptz,
  agent_trace jsonb,
  first_seen_at timestamptz default now(),
  last_seen_by_user_at timestamptz,
  acknowledged_at timestamptz,
  queue_reason text,
  priority_reason text,
  display_name text generated always as (nullif(trim(scout_info ->> 'name'), '')) stored,
  list_one_line text generated always as (nullif(trim(scout_info ->> 'one_line'), '')) stored,
  list_sector text generated always as (nullif(trim(scout_info ->> 'sector'), '')) stored,
  list_scout_type text generated always as (nullif(trim(scout_info ->> 'scout_type'), '')) stored,
  list_origin_type text generated always as (nullif(trim(scout_info ->> 'origin_type'), '')) stored,
  list_lookup_query text generated always as (nullif(trim(scout_info ->> 'lookup_query'), '')) stored,
  list_lookup_website text generated always as (nullif(trim(scout_info ->> 'lookup_website'), '')) stored,
  list_confidence double precision generated always as (
    coalesce(
      case when scout_info ? 'confidence_score'
             and nullif(trim(scout_info ->> 'confidence_score'), '') is not null
           then (scout_info ->> 'confidence_score')::double precision
           else null end,
      0.5
    )
  ) stored,
  list_score double precision generated always as (
    case when review_info is null then null else
      (coalesce((review_info ->> 'market_score')::double precision, 0.0)
       + coalesce((review_info ->> 'product_score')::double precision, 0.0)
       + coalesce((review_info ->> 'technical_score')::double precision, 0.0)
       + coalesce((review_info ->> 'execution_score')::double precision, 0.0)) / 4.0
    end
  ) stored,
  list_verdict text generated always as (nullif(trim(review_info ->> 'verdict'), '')) stored,
  list_consensus_verdict text generated always as (nullif(trim(review_info ->> 'consensus_verdict'), '')) stored,
  list_reviewed_at text generated always as (nullif(trim(review_info ->> 'reviewed_at'), '')) stored,
  list_partnered_at text generated always as (nullif(trim(partner_info ->> 'partnered_at'), '')) stored,
  short_summary text generated always as (left(coalesce(nullif(trim(review_info ->> 'overall_summary'), ''), ''), 400)) stored,
  list_reviewer_disagreement boolean generated always as (
    case when review_info is null then false
      when review_info -> 'reviewer_disagreement' = 'true'::jsonb then true
      when lower(trim(review_info ->> 'reviewer_disagreement')) in ('true', '1', 'yes') then true
      else false end
  ) stored,
  partner_human_review_required boolean generated always as (
    case when partner_info is null then false
      when partner_info -> 'human_review_required' = 'true'::jsonb then true
      when lower(trim(partner_info ->> 'human_review_required')) in ('true', '1', 'yes') then true
      else false end
  ) stored,
  list_lookup_id text generated always as (nullif(trim(scout_info ->> 'lookup_id'), '')) stored,
  partner_decision text generated always as (
    nullif(trim(coalesce(nullif(trim(partner_info ->> 'recommendation'), ''),
                         nullif(trim(partner_info ->> 'decision'), ''))), '')
  ) stored,
  list_location text generated always as (nullif(trim(scout_info ->> 'location'), '')) stored,
  list_resolution_status text generated always as (nullif(trim(scout_info ->> 'resolution_status'), '')) stored
);

create unique index if not exists startups_user_startup_id_idx
  on public.startups (user_id, startup_id);
create index if not exists startups_user_id_idx on public.startups (user_id);
create unique index if not exists startups_user_normalized_display_name_uidx
  on public.startups (user_id, lower(btrim(display_name)))
  where nullif(btrim(display_name), '') is not null;
create index if not exists startups_user_updated_at_desc_idx
  on public.startups (user_id, updated_at desc, startup_id desc);
create index if not exists startups_user_unreviewed_idx
  on public.startups (user_id) where review_info is null;
create index if not exists startups_user_undecided_idx
  on public.startups (user_id) where review_info is not null and partner_info is null;
create index if not exists startups_user_escalation_idx
  on public.startups (user_id) where partner_human_review_required = true;
create index if not exists startups_user_unresolved_idx
  on public.startups (user_id, unresolved_at desc) where unresolved_at is not null;
create index if not exists startups_user_intake_idx
  on public.startups (user_id, acknowledged_at, first_seen_at desc);
create index if not exists startups_user_queue_escalated_idx
  on public.startups (user_id, updated_at desc) where partner_human_review_required = true;
