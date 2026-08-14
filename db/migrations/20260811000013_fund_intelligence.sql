-- Provider-neutral governed fund-intelligence contract.
create table if not exists public.fund_intelligence_settings (
  user_id text primary key,
  settings_version text not null default 'fund-intelligence-v1',
  minimum_override_sample integer not null default 5 check (minimum_override_sample between 1 and 1000),
  preview_row_limit integer not null default 200 check (preview_row_limit between 1 and 1000),
  updated_at timestamptz not null default now()
);
create table if not exists public.learning_signals (
  learning_signal_id uuid primary key default gen_random_uuid(),
  user_id text not null,
  opportunity_id uuid,
  source_type text not null,
  source_id uuid not null,
  signal_type text not null,
  attribution text not null check (attribution in (
    'acquisition_miss','identity_error','evidence_retrieval_gap','extraction_error',
    'claim_verification_error','policy_criterion_disagreement','weight_threshold_disagreement',
    'recommendation_rule_disagreement','private_information_exception','human_strategic_exception','unclassified'
  )),
  strength double precision not null check (strength between 0 and 1),
  detail jsonb not null default '{}'::jsonb,
  observed_at timestamptz not null,
  created_at timestamptz not null default now(),
  unique (user_id, learning_signal_id),
  unique (user_id, source_type, source_id, signal_type),
  foreign key (user_id, opportunity_id) references public.opportunities (user_id, opportunity_id)
);
create table if not exists public.policy_proposals (
  policy_proposal_id uuid primary key default gen_random_uuid(),
  user_id text not null,
  proposal_fingerprint text not null,
  pattern_summary text not null,
  attribution text not null,
  sample_size integer not null check (sample_size >= 1),
  sample_period_start timestamptz,
  sample_period_end timestamptz,
  confidence double precision not null check (confidence between 0 and 1),
  limitations jsonb not null default '[]'::jsonb,
  proposed_policy_patch jsonb not null,
  status text not null check (status in ('draft','ready_for_review','accepted','edited_and_accepted','rejected','deferred','expired')),
  reviewer_rationale text,
  resulting_policy_version_id uuid,
  reviewed_by text,
  reviewed_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id, policy_proposal_id),
  unique (user_id, proposal_fingerprint)
);
create table if not exists public.proposal_signal_links (
  proposal_signal_link_id uuid primary key default gen_random_uuid(),
  user_id text not null,
  policy_proposal_id uuid not null,
  learning_signal_id uuid not null,
  relationship text not null check (relationship in ('supports','contradicts','contextualizes')),
  created_at timestamptz not null default now(),
  unique (user_id, policy_proposal_id, learning_signal_id),
  foreign key (user_id, policy_proposal_id) references public.policy_proposals (user_id, policy_proposal_id),
  foreign key (user_id, learning_signal_id) references public.learning_signals (user_id, learning_signal_id)
);
create table if not exists public.policy_impact_previews (
  policy_impact_preview_id uuid primary key default gen_random_uuid(),
  user_id text not null,
  policy_proposal_id uuid not null,
  sample_size integer not null,
  affected_opportunity_count integer not null,
  opportunity_examples jsonb not null default '[]'::jsonb,
  estimated_effect jsonb not null default '{}'::jsonb,
  limitations jsonb not null default '[]'::jsonb,
  created_by text not null,
  created_at timestamptz not null default now(),
  unique (user_id, policy_impact_preview_id),
  foreign key (user_id, policy_proposal_id) references public.policy_proposals (user_id, policy_proposal_id)
);
create table if not exists public.governed_policy_versions (
  governed_policy_version_id uuid primary key default gen_random_uuid(),
  user_id text not null,
  policy_proposal_id uuid,
  policy_patch jsonb not null,
  status text not null check (status in ('draft','published','superseded')),
  created_by text not null,
  published_by text,
  published_policy_id text,
  published_policy_hash text,
  policy_hash text,
  publication_source text,
  created_at timestamptz not null default now(),
  published_at timestamptz,
  unique (user_id, governed_policy_version_id),
  foreign key (user_id, policy_proposal_id) references public.policy_proposals (user_id, policy_proposal_id)
);
do $$ begin
  if not exists (select 1 from pg_constraint where conname = 'policy_proposals_resulting_version_fk') then
    alter table public.policy_proposals add constraint policy_proposals_resulting_version_fk
      foreign key (user_id, resulting_policy_version_id)
      references public.governed_policy_versions (user_id, governed_policy_version_id);
  end if;
end $$;
create index if not exists learning_signals_pattern_idx on public.learning_signals (user_id, signal_type, attribution, observed_at);
create index if not exists policy_proposals_inbox_idx on public.policy_proposals (user_id, status, created_at desc);
create or replace function public.prevent_learning_signal_mutation()
returns trigger language plpgsql security invoker set search_path = public as $$
begin raise exception 'learning signals and proposal links are append-only'; end;
$$;
drop trigger if exists learning_signals_append_only on public.learning_signals;
create trigger learning_signals_append_only before update or delete on public.learning_signals
for each row execute function public.prevent_learning_signal_mutation();
drop trigger if exists proposal_signal_links_append_only on public.proposal_signal_links;
create trigger proposal_signal_links_append_only before update or delete on public.proposal_signal_links
for each row execute function public.prevent_learning_signal_mutation();
