-- The durable lookup worker is the sole authority for lookup attempt outcomes.
-- Browser/client roles must never read or mutate this operational table.

alter table public.lookup_job_outcomes enable row level security;

drop policy if exists lookup_job_outcomes_service_role_all
  on public.lookup_job_outcomes;
create policy lookup_job_outcomes_service_role_all
  on public.lookup_job_outcomes
  for all
  to service_role
  using (true)
  with check (true);

revoke all on table public.lookup_job_outcomes from public, anon, authenticated;
revoke all on table public.lookup_job_outcomes from service_role;
grant select, insert, update, delete on table public.lookup_job_outcomes to service_role;
