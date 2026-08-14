-- Provider-neutral security counters, locks, and stage cadence claims.
-- Runtime access is through application-owned asyncpg repositories.

create table if not exists public.security_limits (
  key text primary key,
  kind text not null check (kind in ('rate', 'lock')),
  count integer not null default 0,
  window_seconds integer,
  expires_at timestamptz not null,
  lock_owner_token text,
  metadata jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

alter table public.security_limits
  add column if not exists lock_owner_token text;

create index if not exists security_limits_expires_at_idx
  on public.security_limits (expires_at);

create table if not exists public.agent_job_schedules (
  user_id text not null,
  job_name text not null,
  last_claimed_at timestamptz not null,
  primary key (user_id, job_name)
);

create index if not exists agent_job_schedules_claim_idx
  on public.agent_job_schedules (user_id, last_claimed_at);
