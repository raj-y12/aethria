-- Provider-neutral Batch 4A operational state and history.

create table if not exists public.startup_pipeline_state (
  id uuid primary key default gen_random_uuid(),
  user_id text not null,
  startup_id text not null,
  pipeline_run_id uuid not null,
  status text not null,
  updated_at timestamptz not null default timezone('utc', now()),
  error text,
  constraint startup_pipeline_state_status_chk check (
    status in ('pending','ingesting','scouting','processing_signals',
               'generating_memo','writing_memo','ready','failed')
  )
);
create unique index if not exists startup_pipeline_state_user_startup_idx
  on public.startup_pipeline_state (user_id, startup_id);
create index if not exists startup_pipeline_state_user_id_idx
  on public.startup_pipeline_state (user_id);
create index if not exists startup_pipeline_state_run_idx
  on public.startup_pipeline_state (pipeline_run_id);

create table if not exists public.scoring_trails (
  id uuid primary key default gen_random_uuid(),
  user_id text not null,
  startup_id text not null,
  created_at timestamptz not null default now(),
  rubric_version text,
  policy_version_id text,
  policy_hash text,
  overall_score numeric,
  overall_confidence numeric,
  stage_cohort text,
  sector_tam_benchmark text,
  trail jsonb not null
);
create index if not exists scoring_trails_user_startup_created_idx
  on public.scoring_trails (user_id, startup_id, created_at desc);
create index if not exists scoring_trails_user_created_idx
  on public.scoring_trails (user_id, created_at desc);

create table if not exists public.pipeline_activity (
  id uuid primary key default gen_random_uuid(),
  user_id text not null,
  timestamp timestamptz not null default now(),
  startups_found integer not null default 0,
  reviewed_count integer not null default 0,
  decisions_made integer not null default 0,
  escalations_count integer not null default 0
);
create index if not exists pipeline_activity_user_ts
  on public.pipeline_activity (user_id, timestamp desc);
