-- Provider-neutral durable job and lookup outcome contract.
create table if not exists public.agent_jobs (
  job_id uuid primary key default gen_random_uuid(),
  user_id text not null,
  job_type text not null check (job_type in ('pipeline_cycle', 'company_lookup', 'evidence_refresh')),
  idempotency_key text not null check (length(btrim(idempotency_key)) > 0),
  payload jsonb not null default '{}'::jsonb,
  status text not null default 'queued' check (status in ('queued','running','retry_wait','blocked','succeeded','failed','dead_letter','cancelled')),
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
  block_code text,
  block_detail text,
  recovery_action text,
  unique (user_id, idempotency_key),
  unique (user_id, job_id),
  check (attempts <= max_attempts),
  check (block_code is null or block_code ~ '^[a-z][a-z0-9_]{1,79}$')
);

create index if not exists agent_jobs_claim_idx on public.agent_jobs
  (status, next_attempt_at, priority desc, created_at)
  where status in ('queued', 'retry_wait');
create index if not exists agent_jobs_lease_recovery_idx on public.agent_jobs
  (status, lease_expires_at) where status = 'running';
create index if not exists agent_jobs_tenant_status_idx on public.agent_jobs
  (user_id, status, created_at desc);
create index if not exists agent_jobs_blocked_code_idx on public.agent_jobs
  (user_id, block_code, updated_at desc);

create table if not exists public.agent_job_checkpoints (
  checkpoint_id uuid primary key default gen_random_uuid(),
  job_id uuid not null,
  user_id text not null,
  pipeline_run_id uuid not null,
  stage text not null check (length(btrim(stage)) > 0),
  attempt integer not null check (attempt >= 1),
  status text not null check (status in ('started','succeeded','failed','cancelled')),
  output_metadata jsonb not null default '{}'::jsonb,
  error text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id, job_id, stage, attempt, status),
  foreign key (user_id, job_id) references public.agent_jobs (user_id, job_id) on delete cascade
);
create index if not exists agent_job_checkpoints_job_idx on public.agent_job_checkpoints
  (user_id, job_id, attempt, created_at);

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
create index if not exists domain_outbox_unpublished_idx on public.domain_outbox
  (next_attempt_at, created_at) where published_at is null;
create index if not exists domain_outbox_tenant_idx on public.domain_outbox
  (user_id, created_at desc);

create table if not exists public.lookup_job_outcomes (
  user_id text not null,
  id text not null,
  data jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default timezone('utc', now()),
  primary key (user_id, id)
);

create or replace function public.touch_durable_job_updated_at()
returns trigger language plpgsql security invoker set search_path = public as $$
begin
  new.updated_at = now();
  return new;
end;
$$;
drop trigger if exists agent_jobs_touch_updated_at on public.agent_jobs;
create trigger agent_jobs_touch_updated_at before update on public.agent_jobs
for each row execute function public.touch_durable_job_updated_at();
drop trigger if exists agent_job_checkpoints_touch_updated_at on public.agent_job_checkpoints;
create trigger agent_job_checkpoints_touch_updated_at before update on public.agent_job_checkpoints
for each row execute function public.touch_durable_job_updated_at();
