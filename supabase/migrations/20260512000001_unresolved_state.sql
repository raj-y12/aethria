-- Persist unresolved queue state for workgrid and stats.

alter table public.startups
  add column if not exists unresolved_at timestamptz;

update public.startups
set unresolved_at = coalesce(unresolved_at, created_at)
where unresolved_at is null
  and (
    review_info is null
    or partner_info is null
    or (
      partner_human_review_required = true
      and (
        human_resolution is null
        or nullif(trim(human_resolution->>'resolved_at'), '') is null
      )
    )
  );

update public.startups
set unresolved_at = null
where unresolved_at is not null
  and review_info is not null
  and partner_info is not null
  and (
    partner_human_review_required = false
    or nullif(trim(human_resolution->>'resolved_at'), '') is not null
  );

create index if not exists startups_user_unresolved_idx
  on public.startups (user_id, unresolved_at desc)
  where unresolved_at is not null;
