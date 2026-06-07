-- P7.1 — Persist the structured evidence + score trail per decision.
--
-- Stores, for every scored startup, the facts/labels/component scores, the canonical
-- overall, the rubric/policy version it was graded under, and the comparability context
-- (stage cohort, sector TAM benchmark). This is the substrate the outcome → anchor
-- recalibration loop (P7.2) reads later: map historical scores to realized outcomes and
-- re-fit anchors to be predictive.
--
-- Design: an APPEND-ONLY table rather than a JSONB column on public.startups. The
-- startups row is rewritten on every pipeline stage (scout → review → partner → meta);
-- a prior migration deliberately dropped its GIN indexes to cut write amplification, so
-- adding another heavy JSONB column there would reintroduce that cost. A separate table
-- also preserves history (one row per scoring event) instead of overwriting in place,
-- which is exactly what calibration needs.
--
-- Access: written via the service-role client only (the pipeline). RLS is enabled with
-- NO policies, which locks the table to the service role (service_role bypasses RLS) and
-- keeps it off the anon/auth surface — the frontend never touches Supabase directly.

create table if not exists public.scoring_trails (
  id              uuid primary key default gen_random_uuid(),
  user_id         text        not null,
  startup_id      text        not null,
  created_at      timestamptz not null default now(),
  rubric_version      text,
  policy_version_id   text,
  policy_hash         text,
  overall_score       numeric,
  overall_confidence  numeric,
  stage_cohort        text,
  sector_tam_benchmark text,
  -- Full structured scoring trace: raw_signals (facts/labels), per-component scores,
  -- per-dimension aggregates, unscored/qualitative flags. Source of truth for replay.
  trail           jsonb not null
);

-- Primary read path: latest trail(s) for a given user's startup, newest first.
create index if not exists scoring_trails_user_startup_created_idx
  on public.scoring_trails (user_id, startup_id, created_at desc);

-- Calibration scan path: all of a user's trails in a time window.
create index if not exists scoring_trails_user_created_idx
  on public.scoring_trails (user_id, created_at desc);

alter table public.scoring_trails enable row level security;

comment on table public.scoring_trails is
  'Append-only per-decision scoring trail (P7.1): facts, labels, component scores, rubric/policy version, stage cohort, sector benchmark. Service-role only. Read by the P7.2 recalibration loop.';
