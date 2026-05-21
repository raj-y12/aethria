-- Persist row-level queue awareness for newly discovered startups.
-- Priority remains computed by the application; these fields track whether a
-- user has actually seen a company and why it is currently surfaced.

alter table public.startups
  add column if not exists first_seen_at timestamptz default now(),
  add column if not exists last_seen_by_user_at timestamptz,
  add column if not exists acknowledged_at timestamptz,
  add column if not exists queue_reason text,
  add column if not exists priority_reason text;

update public.startups
set first_seen_at = coalesce(first_seen_at, created_at, now())
where first_seen_at is null;

-- Existing rows predate this feature, so mark them acknowledged during the
-- migration. Rows inserted after this migration keep acknowledged_at null
-- until the user opens the memo or records a ruling.
update public.startups
set acknowledged_at = coalesce(acknowledged_at, created_at, now()),
    last_seen_by_user_at = coalesce(last_seen_by_user_at, acknowledged_at, created_at, now())
where acknowledged_at is null;

create index if not exists startups_user_intake_idx
  on public.startups (user_id, acknowledged_at, first_seen_at desc);

create index if not exists startups_user_queue_stale_idx
  on public.startups (user_id, unresolved_at desc)
  where unresolved_at is not null;

create index if not exists startups_user_queue_escalated_idx
  on public.startups (user_id, updated_at desc)
  where partner_human_review_required = true;
