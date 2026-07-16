-- Phase 6: lifecycle service levels, refresh envelopes, cost reservation, and material checks.

alter table public.opportunities
  add column if not exists next_review_at timestamptz,
  add column if not exists lifecycle_reason text;

create table if not exists public.budget_reservations (
  budget_reservation_id uuid primary key default gen_random_uuid(),
  user_id text not null,
  opportunity_id uuid not null,
  job_id uuid,
  reason text not null,
  service_level integer not null check (service_level between 0 and 5),
  max_search_queries integer not null check (max_search_queries between 0 and 100),
  max_artifacts integer not null check (max_artifacts between 0 and 100),
  max_model_tokens integer not null check (max_model_tokens between 0 and 1000000),
  estimated_cost_usd numeric(12,6) not null check (estimated_cost_usd >= 0),
  actual_cost_usd numeric(12,6),
  providers jsonb not null default '[]'::jsonb,
  deadline_at timestamptz not null,
  status text not null check (status in ('reserved','settled','released','expired')),
  expires_at timestamptz not null,
  settled_at timestamptz,
  created_at timestamptz not null default now(),
  unique (user_id, budget_reservation_id),
  unique (user_id, job_id),
  foreign key (user_id, opportunity_id) references public.opportunities (user_id, opportunity_id),
  foreign key (user_id, job_id) references public.agent_jobs (user_id, job_id)
);
create index if not exists budget_reservations_active_idx on public.budget_reservations (user_id, status, expires_at);
create index if not exists opportunities_next_review_idx on public.opportunities (user_id, next_review_at)
  where next_review_at is not null and service_level >= 3;

create table if not exists public.material_change_checks (
  material_change_check_id uuid primary key default gen_random_uuid(),
  user_id text not null,
  opportunity_id uuid not null,
  job_id uuid,
  reason text not null,
  previous_snapshot_hash text,
  current_snapshot_hash text,
  material_change boolean not null,
  detail jsonb not null default '{}'::jsonb,
  checked_at timestamptz not null default now(),
  unique (user_id, material_change_check_id),
  foreign key (user_id, opportunity_id) references public.opportunities (user_id, opportunity_id),
  foreign key (user_id, job_id) references public.agent_jobs (user_id, job_id)
);

alter table public.agent_jobs drop constraint if exists agent_jobs_job_type_check;
alter table public.agent_jobs add constraint agent_jobs_job_type_check
  check (job_type in ('pipeline_cycle','company_lookup','evidence_refresh'));

alter table public.budget_reservations enable row level security;
alter table public.material_change_checks enable row level security;
create policy budget_reservations_service_role_all on public.budget_reservations for all to service_role using (true) with check (true);
create policy material_change_checks_service_role_all on public.material_change_checks for all to service_role using (true) with check (true);
revoke all on table public.budget_reservations, public.material_change_checks from anon, authenticated;
grant select, insert, update, delete on table public.budget_reservations, public.material_change_checks to service_role;
