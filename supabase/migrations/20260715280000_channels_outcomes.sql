-- Phase 8: bounded channel imports and evidence-backed, non-causal outcomes.

alter table public.source_observations drop constraint if exists source_observations_channel_check;
alter table public.source_observations add constraint source_observations_channel_check
  check (channel in (
    'manual_lookup','autonomous_discovery','inbound','outbound','referral','event',
    'portfolio_intro','import','crm_import','backfill'
  ));

create table if not exists public.import_batches (
  import_batch_id uuid primary key default gen_random_uuid(),
  user_id text not null,
  idempotency_key text not null,
  source text not null check (source in ('csv','crm_csv','event_csv','referral_csv')),
  file_hash text not null,
  field_mapping jsonb not null,
  status text not null check (status in ('pending','processing','completed','completed_with_errors','failed')),
  row_count integer not null check (row_count between 0 and 500),
  resolved_count integer not null default 0,
  review_count integer not null default 0,
  error_count integer not null default 0,
  created_by text not null,
  completed_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id, import_batch_id),
  unique (user_id, idempotency_key)
);

create table if not exists public.import_rows (
  import_row_id uuid primary key default gen_random_uuid(),
  user_id text not null,
  import_batch_id uuid not null,
  row_number integer not null,
  row_key text not null,
  source_observation_id uuid,
  company_id uuid,
  opportunity_id uuid,
  identity_case_id uuid,
  status text not null check (status in ('resolved','review_required','error')),
  error_code text,
  created_at timestamptz not null default now(),
  unique (user_id, import_row_id),
  unique (user_id, import_batch_id, row_key),
  foreign key (user_id, import_batch_id) references public.import_batches (user_id, import_batch_id),
  foreign key (user_id, source_observation_id) references public.source_observations (user_id, observation_id),
  foreign key (user_id, company_id) references public.companies (user_id, company_id),
  foreign key (user_id, opportunity_id) references public.opportunities (user_id, opportunity_id),
  foreign key (user_id, identity_case_id) references public.identity_resolution_cases (user_id, identity_case_id)
);

create table if not exists public.outcome_observations (
  outcome_observation_id uuid primary key default gen_random_uuid(),
  user_id text not null,
  company_id uuid not null,
  opportunity_id uuid,
  outcome_type text not null check (outcome_type in (
    'financing','revenue_milestone','customer_milestone','product_launch',
    'acquisition','shutdown','leadership_change','follow_on_decision','other'
  )),
  valence text not null check (valence in ('positive','negative','neutral','mixed')),
  summary text not null check (length(btrim(summary)) between 3 and 2000),
  verification_state text not null check (verification_state in ('unverified','verified','disputed')),
  materiality integer not null check (materiality between 1 and 5),
  effective_at timestamptz,
  observed_at timestamptz not null,
  recorded_by text not null,
  supersedes_outcome_id uuid,
  created_at timestamptz not null default now(),
  unique (user_id, outcome_observation_id),
  foreign key (user_id, company_id) references public.companies (user_id, company_id),
  foreign key (user_id, opportunity_id) references public.opportunities (user_id, opportunity_id),
  foreign key (user_id, supersedes_outcome_id) references public.outcome_observations (user_id, outcome_observation_id)
);

create table if not exists public.outcome_evidence_links (
  outcome_evidence_link_id uuid primary key default gen_random_uuid(),
  user_id text not null,
  outcome_observation_id uuid not null,
  artifact_id uuid not null,
  created_at timestamptz not null default now(),
  unique (user_id, outcome_observation_id, artifact_id),
  foreign key (user_id, outcome_observation_id) references public.outcome_observations (user_id, outcome_observation_id),
  foreign key (user_id, artifact_id) references public.evidence_artifacts (user_id, artifact_id)
);

create index if not exists import_batches_status_idx on public.import_batches (user_id,status,created_at desc);
create index if not exists outcome_observations_company_idx on public.outcome_observations (user_id,company_id,observed_at desc);

create or replace function public.prevent_outcome_mutation()
returns trigger language plpgsql security invoker set search_path=public as $$
begin
  raise exception 'outcome observations are append-only; append a superseding observation';
end;
$$;
drop trigger if exists outcome_observations_append_only on public.outcome_observations;
create trigger outcome_observations_append_only before update or delete on public.outcome_observations
for each row execute function public.prevent_outcome_mutation();

alter table public.import_batches enable row level security;
alter table public.import_rows enable row level security;
alter table public.outcome_observations enable row level security;
alter table public.outcome_evidence_links enable row level security;
create policy import_batches_service_role_all on public.import_batches for all to service_role using (true) with check (true);
create policy import_rows_service_role_all on public.import_rows for all to service_role using (true) with check (true);
create policy outcome_observations_service_role_all on public.outcome_observations for all to service_role using (true) with check (true);
create policy outcome_evidence_links_service_role_all on public.outcome_evidence_links for all to service_role using (true) with check (true);
revoke all on table public.import_batches,public.import_rows,public.outcome_observations,public.outcome_evidence_links from anon,authenticated;
grant select,insert,update,delete on table public.import_batches,public.import_rows,public.outcome_observations,public.outcome_evidence_links to service_role;
revoke all on function public.prevent_outcome_mutation() from public;
grant execute on function public.prevent_outcome_mutation() to service_role;
