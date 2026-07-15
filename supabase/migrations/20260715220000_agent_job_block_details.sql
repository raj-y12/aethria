-- Structured operator-action blocks for durable jobs. A blocked job is neither
-- failed nor automatically retryable; the recovery action is safe to expose.

alter table public.agent_jobs
  add column if not exists block_code text,
  add column if not exists block_detail text,
  add column if not exists recovery_action text;

alter table public.agent_jobs
  drop constraint if exists agent_jobs_block_code_shape;
alter table public.agent_jobs
  add constraint agent_jobs_block_code_shape check (
    block_code is null or block_code ~ '^[a-z][a-z0-9_]{1,79}$'
  );

create index if not exists agent_jobs_blocked_code_idx
  on public.agent_jobs (user_id, block_code, updated_at desc)
  where status = 'blocked';
