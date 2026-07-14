-- Cache the JWT lookup once per statement so the ownership policy does not
-- re-evaluate auth.jwt() for every candidate row.
drop policy if exists "Users read own agent job schedules" on public.agent_job_schedules;
create policy "Users read own agent job schedules"
on public.agent_job_schedules
for select
using ((select auth.jwt()) ->> 'sub' = user_id);
