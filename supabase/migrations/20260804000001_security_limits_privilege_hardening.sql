-- Harden the backend-only rate-limit and lock RPC boundary.

alter function public.security_check_rate_limit(text, integer)
  set search_path = '';

alter function public.security_acquire_lock(text, integer)
  set search_path = '';

alter function public.security_release_lock(text)
  set search_path = '';

revoke all on function public.security_check_rate_limit(
  text, integer
) from public, anon, authenticated;

grant execute on function public.security_check_rate_limit(
  text, integer
) to service_role;

revoke all on function public.security_acquire_lock(
  text, integer
) from public, anon, authenticated;

grant execute on function public.security_acquire_lock(
  text, integer
) to service_role;

revoke all on function public.security_release_lock(text)
from public, anon, authenticated;

grant execute on function public.security_release_lock(text)
to service_role;

alter table public.security_limits enable row level security;

drop policy if exists security_limits_service_role_all
  on public.security_limits;
create policy security_limits_service_role_all
  on public.security_limits
  for all
  to service_role
  using (true)
  with check (true);

revoke all on table public.security_limits from public, anon, authenticated;
revoke all on table public.security_limits from service_role;
grant select, insert, update, delete on table public.security_limits to service_role;
