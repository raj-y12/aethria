-- Provider-neutral imports, outcomes, triage, and canonical portfolio projections.

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
  outcome_type text not null check (outcome_type in ('financing','revenue_milestone','customer_milestone','product_launch','acquisition','shutdown','leadership_change','follow_on_decision','other')),
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
create index if not exists import_batches_status_idx
  on public.import_batches (user_id, status, created_at desc);
create index if not exists outcome_observations_company_idx
  on public.outcome_observations (user_id, company_id, observed_at desc);

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

create table if not exists public.triage_assessments (
  assessment_id uuid primary key default gen_random_uuid(),
  user_id text not null,
  opportunity_id uuid not null,
  disposition text not null check (disposition in ('deep_review','light_monitor','insufficient_evidence','out_of_mandate','archive_candidate')),
  reasons jsonb not null default '[]'::jsonb,
  observation_ids jsonb not null default '[]'::jsonb,
  missing_information jsonb not null default '[]'::jsonb,
  thesis_version_id text not null,
  policy_version_id text not null,
  trigger text not null,
  priority integer not null check (priority between 0 and 100),
  confidence double precision not null check (confidence between 0 and 1),
  created_at timestamptz not null default now(),
  unique (user_id, assessment_id),
  foreign key (user_id, opportunity_id) references public.opportunities (user_id, opportunity_id)
);
create index if not exists triage_assessments_queue_idx
  on public.triage_assessments (user_id, disposition, priority desc, created_at desc);

create table if not exists public.canonical_portfolio_positions (
  position_id uuid primary key default gen_random_uuid(),
  user_id text not null,
  opportunity_id uuid not null,
  company_id uuid not null,
  ruling_id uuid not null,
  status text not null default 'active' check (status in ('active','exited','written_off')),
  entry_rationale text not null,
  investor_confidence double precision not null check (investor_confidence between 0 and 1),
  entered_at timestamptz not null default now(),
  exited_at timestamptz,
  metadata jsonb not null default '{}'::jsonb,
  unique (user_id, position_id),
  unique (user_id, opportunity_id),
  foreign key (user_id, opportunity_id) references public.opportunities (user_id, opportunity_id),
  foreign key (user_id, company_id) references public.companies (user_id, company_id),
  foreign key (user_id, ruling_id) references public.human_rulings (user_id, ruling_id)
);
create index if not exists canonical_portfolio_positions_tenant_status_idx
  on public.canonical_portfolio_positions (user_id, status, entered_at desc);

create or replace function public.prevent_outcome_mutation()
returns trigger language plpgsql security invoker set search_path = public as $$
begin
  raise exception 'outcome observations are append-only; append a superseding observation';
end;
$$;
drop trigger if exists outcome_observations_append_only on public.outcome_observations;
create trigger outcome_observations_append_only before update or delete on public.outcome_observations
for each row execute function public.prevent_outcome_mutation();
