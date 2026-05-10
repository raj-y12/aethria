-- Single-user institutional conviction state.
-- Today rows remain user-owned; a future org/fund owner can move this JSON into
-- a fund-scoped table without changing the payload shape.

alter table public.startups
  add column if not exists conviction_state jsonb;

create index if not exists startups_conviction_state_gin_idx
  on public.startups using gin (conviction_state);
