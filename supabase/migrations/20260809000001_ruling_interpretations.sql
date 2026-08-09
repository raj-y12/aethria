-- Aethria-owned, append-only interpretations of human ruling rationale.

create table if not exists public.ruling_interpretations (
  interpretation_id uuid primary key default gen_random_uuid(),
  user_id text not null,
  ruling_id uuid not null,
  opportunity_id uuid not null,
  recommendation_id uuid,
  evaluation_id uuid,
  version integer not null check (version >= 1),
  source text not null check (source in ('aethria_inferred','operator_correction')),
  status text not null check (status in ('complete','insufficient')),
  rationale_sha256 text not null,
  extraction_confidence double precision not null check (extraction_confidence between 0 and 1),
  positive_factors jsonb not null default '[]'::jsonb,
  negative_factors jsonb not null default '[]'::jsonb,
  accepted_risks jsonb not null default '[]'::jsonb,
  decisive_factors jsonb not null default '[]'::jsonb,
  overridden_criteria jsonb not null default '[]'::jsonb,
  strategic_exception jsonb,
  agreement_with_aethria text not null check (agreement_with_aethria in ('agree','disagree','mixed','unknown')),
  human_confidence double precision,
  evidence_influence jsonb not null default '{"status":"unknown","references":[],"limitations":[]}'::jsonb,
  provenance jsonb not null default '{}'::jsonb,
  correction_note text,
  supersedes_interpretation_id uuid,
  created_at timestamptz not null default now(),
  unique (user_id, interpretation_id),
  unique (user_id, ruling_id, version),
  foreign key (user_id, ruling_id) references public.human_rulings (user_id, ruling_id),
  foreign key (user_id, opportunity_id) references public.opportunities (user_id, opportunity_id),
  foreign key (user_id, recommendation_id) references public.recommendations (user_id, recommendation_id),
  foreign key (user_id, evaluation_id) references public.evaluation_runs (user_id, evaluation_id),
  foreign key (user_id, supersedes_interpretation_id)
    references public.ruling_interpretations (user_id, interpretation_id)
);

create index if not exists ruling_interpretations_ruling_idx
  on public.ruling_interpretations (user_id, ruling_id, version desc);
create index if not exists ruling_interpretations_opportunity_idx
  on public.ruling_interpretations (user_id, opportunity_id, created_at desc);

create or replace function public.prevent_ruling_interpretation_mutation()
returns trigger language plpgsql security invoker set search_path=public as $$
begin
  raise exception 'ruling interpretations are append-only; insert a correction version';
end;
$$;

create trigger ruling_interpretations_append_only
before update or delete on public.ruling_interpretations
for each row execute function public.prevent_ruling_interpretation_mutation();

alter table public.ruling_interpretations enable row level security;
create policy ruling_interpretations_service_role_all on public.ruling_interpretations
  for all to service_role using (true) with check (true);
revoke all on table public.ruling_interpretations from anon, authenticated;
grant select, insert on table public.ruling_interpretations to service_role;
revoke all on function public.prevent_ruling_interpretation_mutation() from public;
grant execute on function public.prevent_ruling_interpretation_mutation() to service_role;
