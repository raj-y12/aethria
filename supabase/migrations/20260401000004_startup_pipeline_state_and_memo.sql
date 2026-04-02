-- Pipeline state per startup per user + persisted display memo (Supabase multi-tenant).
-- Service role writes from workers; RLS mirrors startups pattern.

alter table public.startups
  add column if not exists investment_memo_markdown text;

create table if not exists public.startup_pipeline_state (
  id uuid primary key default gen_random_uuid(),
  user_id text not null,
  startup_id text not null,
  pipeline_run_id uuid not null,
  status text not null,
  updated_at timestamptz not null default timezone('utc', now()),
  error text,
  constraint startup_pipeline_state_status_chk check (
    status in (
      'pending',
      'ingesting',
      'scouting',
      'processing_signals',
      'generating_memo',
      'writing_memo',
      'ready',
      'failed'
    )
  )
);

create unique index if not exists startup_pipeline_state_user_startup_idx
  on public.startup_pipeline_state (user_id, startup_id);

create index if not exists startup_pipeline_state_user_id_idx
  on public.startup_pipeline_state (user_id);

create index if not exists startup_pipeline_state_run_idx
  on public.startup_pipeline_state (pipeline_run_id);

alter table public.startup_pipeline_state enable row level security;

drop policy if exists "Users read own startup_pipeline_state" on public.startup_pipeline_state;
create policy "Users read own startup_pipeline_state"
  on public.startup_pipeline_state for select
  using (auth.jwt() ->> 'sub' = user_id);

drop policy if exists "Service role full access startup_pipeline_state" on public.startup_pipeline_state;
create policy "Service role full access startup_pipeline_state"
  on public.startup_pipeline_state for all
  using (auth.role() = 'service_role')
  with check (auth.role() = 'service_role');
