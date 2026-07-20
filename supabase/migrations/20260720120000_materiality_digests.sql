-- Separate reproducible evaluation snapshots from clock-independent content checks.

alter table public.evaluation_runs
  add column if not exists evidence_materiality_digest text;

alter table public.material_change_checks
  add column if not exists previous_materiality_digest text,
  add column if not exists current_materiality_digest text;

comment on column public.evaluation_runs.evidence_snapshot_hash is
  'Clocked hash of the exact immutable evaluation snapshot.';
comment on column public.evaluation_runs.evidence_materiality_digest is
  'Clock-independent hash of the enriched decision-bearing claim/evidence content.';
comment on column public.material_change_checks.previous_materiality_digest is
  'Prior clock-independent enriched content digest.';
comment on column public.material_change_checks.current_materiality_digest is
  'Current clock-independent enriched content digest.';
