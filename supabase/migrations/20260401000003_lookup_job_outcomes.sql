-- Per-user on-demand lookup failure outcomes (worker writes; GET /api/startups/lookup-status reads).
-- Matches list table shape used by supabase_doc_store.list_upsert / list_get_by_id.

create table if not exists public.lookup_job_outcomes (
  user_id text not null,
  id text not null,
  data jsonb not null default '{}',
  created_at timestamptz not null default timezone('utc', now()),
  primary key (user_id, id)
);

create index if not exists lookup_job_outcomes_user_id_idx on public.lookup_job_outcomes (user_id);
