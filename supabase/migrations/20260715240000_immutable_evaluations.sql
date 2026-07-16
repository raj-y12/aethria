-- Phase 4: immutable claim-snapshot evaluations, criterion assessments, and recommendations.

create table if not exists public.evaluation_runs (
  evaluation_id uuid primary key default gen_random_uuid(),
  user_id text not null,
  opportunity_id uuid not null,
  trigger_type text not null,
  actor_id text not null,
  evidence_snapshot_hash text not null,
  claim_snapshot jsonb not null,
  thesis_version_id text,
  policy_version_id text not null,
  policy_hash text not null,
  rubric_version text not null,
  partner_rules_version text not null,
  partner_rules_hash text not null,
  model_manifest jsonb not null default '{}'::jsonb,
  prompt_manifest jsonb not null default '{}'::jsonb,
  status text not null check (status in ('running','completed','failed')),
  failure_code text,
  supersedes_evaluation_id uuid,
  started_at timestamptz not null default now(),
  completed_at timestamptz,
  created_at timestamptz not null default now(),
  unique (user_id, evaluation_id),
  foreign key (user_id, opportunity_id) references public.opportunities (user_id, opportunity_id),
  foreign key (user_id, supersedes_evaluation_id) references public.evaluation_runs (user_id, evaluation_id)
);
create index if not exists evaluation_runs_opportunity_idx on public.evaluation_runs (user_id, opportunity_id, created_at desc);

create table if not exists public.criterion_assessments (
  criterion_assessment_id uuid primary key default gen_random_uuid(),
  user_id text not null,
  evaluation_id uuid not null,
  criterion text not null,
  score double precision check (score is null or score between 0 and 10),
  confidence double precision not null check (confidence between 0 and 1),
  evidence_sufficiency text not null check (evidence_sufficiency in ('sufficient','partial','insufficient')),
  reasoning text not null,
  supporting_claim_ids jsonb not null default '[]'::jsonb,
  contradicting_claim_ids jsonb not null default '[]'::jsonb,
  missing_evidence jsonb not null default '[]'::jsonb,
  quality_flags jsonb not null default '[]'::jsonb,
  deterministic_adjustments jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  unique (user_id, criterion_assessment_id),
  unique (user_id, evaluation_id, criterion),
  foreign key (user_id, evaluation_id) references public.evaluation_runs (user_id, evaluation_id) on delete cascade
);

create table if not exists public.recommendations (
  recommendation_id uuid primary key default gen_random_uuid(),
  user_id text not null,
  opportunity_id uuid not null,
  evaluation_id uuid not null,
  recommended_state text not null check (recommended_state in ('advance','monitor','pass','insufficient_evidence')),
  attention_priority integer not null check (attention_priority between 0 and 100),
  confidence double precision not null check (confidence between 0 and 1),
  decision_drivers jsonb not null default '[]'::jsonb,
  principal_risks jsonb not null default '[]'::jsonb,
  mandate_conflicts jsonb not null default '[]'::jsonb,
  missing_information jsonb not null default '[]'::jsonb,
  change_conditions jsonb not null default '[]'::jsonb,
  human_review_required boolean not null default true,
  previous_recommendation_id uuid,
  change_explanation text,
  created_at timestamptz not null default now(),
  unique (user_id, recommendation_id),
  unique (user_id, evaluation_id),
  foreign key (user_id, opportunity_id) references public.opportunities (user_id, opportunity_id),
  foreign key (user_id, evaluation_id) references public.evaluation_runs (user_id, evaluation_id),
  foreign key (user_id, previous_recommendation_id) references public.recommendations (user_id, recommendation_id)
);
create index if not exists recommendations_opportunity_idx on public.recommendations (user_id, opportunity_id, created_at desc);

alter table public.opportunities
  add column if not exists attention_priority integer not null default 0
    check (attention_priority between 0 and 100);

do $$
begin
  if not exists (select 1 from pg_constraint where conname = 'opportunities_current_evaluation_fk') then
    alter table public.opportunities add constraint opportunities_current_evaluation_fk
      foreign key (user_id, current_evaluation_id)
      references public.evaluation_runs (user_id, evaluation_id);
  end if;
  if not exists (select 1 from pg_constraint where conname = 'opportunities_current_recommendation_fk') then
    alter table public.opportunities add constraint opportunities_current_recommendation_fk
      foreign key (user_id, current_recommendation_id)
      references public.recommendations (user_id, recommendation_id);
  end if;
end $$;

create or replace function public.prevent_completed_evaluation_mutation()
returns trigger language plpgsql security invoker set search_path = public as $$
begin
  if tg_op = 'DELETE' or old.status = 'completed' then
    raise exception 'completed evaluations are immutable';
  end if;
  return new;
end;
$$;

create or replace function public.prevent_immutable_decision_child_mutation()
returns trigger language plpgsql security invoker set search_path = public as $$
begin
  raise exception 'evaluation assessments and recommendations are immutable';
end;
$$;

create trigger evaluation_runs_immutable before update or delete on public.evaluation_runs
for each row execute function public.prevent_completed_evaluation_mutation();
create trigger criterion_assessments_immutable before update or delete on public.criterion_assessments
for each row execute function public.prevent_immutable_decision_child_mutation();
create trigger recommendations_immutable before update or delete on public.recommendations
for each row execute function public.prevent_immutable_decision_child_mutation();

alter table public.evaluation_runs enable row level security;
alter table public.criterion_assessments enable row level security;
alter table public.recommendations enable row level security;
create policy evaluation_runs_service_role_all on public.evaluation_runs for all to service_role using (true) with check (true);
create policy criterion_assessments_service_role_all on public.criterion_assessments for all to service_role using (true) with check (true);
create policy recommendations_service_role_all on public.recommendations for all to service_role using (true) with check (true);
revoke all on table public.evaluation_runs, public.criterion_assessments, public.recommendations from anon, authenticated;
grant select, insert, update, delete on table public.evaluation_runs, public.criterion_assessments, public.recommendations to service_role;
revoke all on function public.prevent_completed_evaluation_mutation(), public.prevent_immutable_decision_child_mutation() from public;
grant execute on function public.prevent_completed_evaluation_mutation(), public.prevent_immutable_decision_child_mutation() to service_role;
