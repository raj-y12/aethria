-- Startup identity aliases are service-role-only compatibility data.
alter table public.startup_id_aliases enable row level security;

drop policy if exists startup_id_aliases_service_role_all
  on public.startup_id_aliases;
create policy startup_id_aliases_service_role_all
  on public.startup_id_aliases
  for all to service_role
  using (true)
  with check (true);

revoke all on table public.startup_id_aliases from anon, authenticated;
grant select, insert, update, delete on table public.startup_id_aliases to service_role;
