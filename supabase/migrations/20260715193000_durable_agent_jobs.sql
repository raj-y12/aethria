-- Transactional accepted-work substrate for pipeline cycles and company lookups.
-- Workers use direct PostgreSQL transactions and SKIP LOCKED; these tables are
-- not a PostgREST lease protocol.

create extension if not exists pgcrypto;

create table if not exists public.agent_jobs (
  job_id uuid primary key default gen_random_uuid(),
  user_id text not null,
  job_type text not null check (job_type in ('pipeline_cycle', 'company_lookup')),
  idempotency_key text not null check (length(btrim(idempotency_key)) > 0),
  payload jsonb not null default '{}'::jsonb,
  status text not null default 'queued' check (
    status in (
      'queued', 'running', 'retry_wait', 'blocked', 'succeeded', 'failed',
      'dead_letter', 'cancelled'
    )
  ),
  priority integer not null default 0,
  attempts integer not null default 0 check (attempts >= 0),
  max_attempts integer not null default 3 check (max_attempts >= 1),
  lease_owner text,
  lease_expires_at timestamptz,
  heartbeat_at timestamptz,
  next_attempt_at timestamptz not null default now(),
  pipeline_run_id uuid not null default gen_random_uuid(),
  last_error text,
  accepted_at timestamptz not null default now(),
  started_at timestamptz,
  completed_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id, idempotency_key),
  unique (user_id, job_id),
  check (attempts <= max_attempts)
);

create index if not exists agent_jobs_claim_idx
  on public.agent_jobs (status, next_attempt_at, priority desc, created_at)
  where status in ('queued', 'retry_wait');

create index if not exists agent_jobs_lease_recovery_idx
  on public.agent_jobs (status, lease_expires_at)
  where status = 'running';

create index if not exists agent_jobs_tenant_status_idx
  on public.agent_jobs (user_id, status, created_at desc);

create table if not exists public.agent_job_checkpoints (
  checkpoint_id uuid primary key default gen_random_uuid(),
  job_id uuid not null,
  user_id text not null,
  pipeline_run_id uuid not null,
  stage text not null check (length(btrim(stage)) > 0),
  attempt integer not null check (attempt >= 1),
  status text not null check (status in ('started', 'succeeded', 'failed', 'cancelled')),
  output_metadata jsonb not null default '{}'::jsonb,
  error text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id, job_id, stage, attempt, status),
  foreign key (user_id, job_id)
    references public.agent_jobs (user_id, job_id)
    on delete cascade
);

create index if not exists agent_job_checkpoints_job_idx
  on public.agent_job_checkpoints (user_id, job_id, attempt, created_at);

create table if not exists public.domain_outbox (
  event_id uuid primary key default gen_random_uuid(),
  user_id text not null,
  aggregate_type text not null check (length(btrim(aggregate_type)) > 0),
  aggregate_id text not null check (length(btrim(aggregate_id)) > 0),
  event_type text not null check (length(btrim(event_type)) > 0),
  event_version integer not null default 1 check (event_version >= 1),
  payload jsonb not null default '{}'::jsonb,
  publication_attempts integer not null default 0 check (publication_attempts >= 0),
  next_attempt_at timestamptz not null default now(),
  published_at timestamptz,
  last_error text,
  created_at timestamptz not null default now()
);

create index if not exists domain_outbox_unpublished_idx
  on public.domain_outbox (next_attempt_at, created_at)
  where published_at is null;

create index if not exists domain_outbox_tenant_idx
  on public.domain_outbox (user_id, created_at desc);

create or replace function public.touch_durable_job_updated_at()
returns trigger
language plpgsql
security invoker
set search_path = public
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists agent_jobs_touch_updated_at on public.agent_jobs;
create trigger agent_jobs_touch_updated_at
before update on public.agent_jobs
for each row execute function public.touch_durable_job_updated_at();

drop trigger if exists agent_job_checkpoints_touch_updated_at on public.agent_job_checkpoints;
create trigger agent_job_checkpoints_touch_updated_at
before update on public.agent_job_checkpoints
for each row execute function public.touch_durable_job_updated_at();

alter table public.agent_jobs enable row level security;
alter table public.agent_job_checkpoints enable row level security;
alter table public.domain_outbox enable row level security;

drop policy if exists agent_jobs_service_role_all on public.agent_jobs;
create policy agent_jobs_service_role_all on public.agent_jobs
  for all to service_role using (true) with check (true);

drop policy if exists agent_job_checkpoints_service_role_all on public.agent_job_checkpoints;
create policy agent_job_checkpoints_service_role_all on public.agent_job_checkpoints
  for all to service_role using (true) with check (true);

drop policy if exists domain_outbox_service_role_all on public.domain_outbox;
create policy domain_outbox_service_role_all on public.domain_outbox
  for all to service_role using (true) with check (true);

revoke all on table public.agent_jobs from anon, authenticated;
revoke all on table public.agent_job_checkpoints from anon, authenticated;
revoke all on table public.domain_outbox from anon, authenticated;
revoke all on function public.touch_durable_job_updated_at() from public;

grant select, insert, update, delete on table public.agent_jobs to service_role;
grant select, insert, update, delete on table public.agent_job_checkpoints to service_role;
grant select, insert, update, delete on table public.domain_outbox to service_role;
grant execute on function public.touch_durable_job_updated_at() to service_role;
