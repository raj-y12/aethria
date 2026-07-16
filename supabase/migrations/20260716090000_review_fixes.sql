-- Code-review fixes: give every resolved source observation a stable link to
-- the exact opportunity it admitted. The previous latest_observation join made
-- idempotent replays lose their opportunity as soon as a newer source arrived.

alter table public.source_observations
  add column if not exists opportunity_id uuid;

-- Exact historical relationships can be recovered from the opportunity's
-- boundary observations. For a company with one opportunity, all remaining
-- observations are unambiguous and can be recovered safely as well.
update public.source_observations o
set opportunity_id = p.opportunity_id
from public.opportunities p
where o.user_id = p.user_id
  and o.company_id = p.company_id
  and o.opportunity_id is null
  and o.observation_id in (p.first_observation_id, p.latest_observation_id);

update public.source_observations o
set opportunity_id = p.opportunity_id
from public.opportunities p
where o.user_id = p.user_id
  and o.company_id = p.company_id
  and o.opportunity_id is null
  and not exists (
    select 1
    from public.opportunities other
    where other.user_id = p.user_id
      and other.company_id = p.company_id
      and other.opportunity_id <> p.opportunity_id
  );

do $$
begin
  if not exists (
    select 1 from pg_constraint
    where conname = 'source_observations_opportunity_fk'
  ) then
    alter table public.source_observations
      add constraint source_observations_opportunity_fk
      foreign key (user_id, opportunity_id)
      references public.opportunities (user_id, opportunity_id);
  end if;
end $$;

create index if not exists source_observations_opportunity_idx
  on public.source_observations (user_id, opportunity_id, observed_at desc)
  where opportunity_id is not null;

alter table public.governed_policy_versions
  add column if not exists policy_hash text;

alter table public.governed_policy_versions
  add constraint governed_policy_versions_policy_hash_present
  check (policy_hash is not null and length(btrim(policy_hash)) > 0)
  not valid;
