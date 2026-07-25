-- Immutable, versioned routing decisions for every resolved opportunity.
create table if not exists public.triage_assessments (
  assessment_id uuid primary key default gen_random_uuid(),
  user_id text not null,
  opportunity_id uuid not null,
  disposition text not null check (disposition in ('deep_review','light_monitor','insufficient_evidence','out_of_mandate','archive_candidate')),
  reasons jsonb not null default '[]'::jsonb,
  observation_ids jsonb not null default '[]'::jsonb,
  missing_information jsonb not null default '[]'::jsonb,
  thesis_version_id text not null,
  policy_version_id text not null,
  trigger text not null,
  priority integer not null check (priority between 0 and 100),
  confidence double precision not null check (confidence between 0 and 1),
  created_at timestamptz not null default now(),
  unique (user_id, assessment_id),
  foreign key (user_id, opportunity_id) references public.opportunities (user_id, opportunity_id)
);
create index if not exists triage_assessments_queue_idx on public.triage_assessments (user_id, disposition, priority desc, created_at desc);
alter table public.triage_assessments enable row level security;
drop policy if exists triage_assessments_service_role_all on public.triage_assessments;
create policy triage_assessments_service_role_all on public.triage_assessments for all to service_role using (true) with check (true);
