-- Step 8.5: immutable audit metadata for derived judgment guards.
alter table public.evaluation_runs
  add column if not exists judgment_audit jsonb not null default '{}'::jsonb;

-- Completed evaluation rows remain immutable under the existing evaluation_runs_immutable trigger.
