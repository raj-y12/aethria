-- Persist structured Scout -> Reviewer -> Partner handoff trace per startup.
-- Embedded JSON keeps MVP operations simple; promote to append-only events later if needed.

alter table public.startups
  add column if not exists agent_trace jsonb;

create index if not exists startups_user_agent_trace_gin_idx
  on public.startups using gin (agent_trace)
  where agent_trace is not null;
