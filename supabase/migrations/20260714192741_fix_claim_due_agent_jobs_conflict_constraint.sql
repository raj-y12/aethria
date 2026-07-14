-- Production verification exposed ambiguity between the table-return output
-- variable `job_name` and the unqualified ON CONFLICT column. Recreate the
-- RPC with the primary-key constraint as the conflict target.
create or replace function public.claim_due_agent_jobs(
  p_user_id text,
  p_intervals jsonb,
  p_now timestamptz default clock_timestamp()
)
returns table(job_name text)
language plpgsql
security invoker
set search_path = ''
as $$
declare
  candidate record;
  claimed_name text;
begin
  if p_user_id is null or btrim(p_user_id) = '' then
    raise exception 'p_user_id is required';
  end if;

  for candidate in
    select key as name, greatest(0, (value #>> '{}')::integer) as interval_seconds
    from jsonb_each(p_intervals)
    order by key
  loop
    claimed_name := null;
    insert into public.agent_job_schedules
      (user_id, job_name, last_claimed_at)
    values
      (p_user_id, candidate.name, p_now)
    on conflict on constraint agent_job_schedules_pkey do update
      set last_claimed_at = excluded.last_claimed_at
      where agent_job_schedules.last_claimed_at
        < excluded.last_claimed_at - make_interval(secs => candidate.interval_seconds)
    returning agent_job_schedules.job_name into claimed_name;

    if claimed_name is not null then
      job_name := claimed_name;
      return next;
    end if;
  end loop;
end;
$$;

revoke all on function public.claim_due_agent_jobs(text, jsonb, timestamptz) from public;
revoke all on function public.claim_due_agent_jobs(text, jsonb, timestamptz) from anon;
revoke all on function public.claim_due_agent_jobs(text, jsonb, timestamptz) from authenticated;
grant execute on function public.claim_due_agent_jobs(text, jsonb, timestamptz) to service_role;
