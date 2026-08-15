-- Quarantine pre-contract lookup outcome rows.
--
-- public.lookup_job_outcomes is read by DurableJobRepository.latest_lookup_attempt
-- under a strict LookupAttemptOutcome contract, but the table was also written
-- through the legacy untyped document path. Rows in the old shape
-- ({id, lookup_id, status, message, failed_at}) fail validation, and because the
-- reader raises LookupOutcomeCorrupt when ANY row for a lookup_id is invalid,
-- GET /api/startups/lookup-status returned a permanent 500 for every affected
-- lookup. The frontend then reported the dispatch as failed while the pipeline
-- kept running.
--
-- Legacy rows are moved, not deleted: they are historical execution records and
-- ADR-0003 forbids destroying tenant rows. The reader is separately taught to
-- classify an old shape as legacy rather than as a contract violation.

create table if not exists public.lookup_job_outcomes_legacy (
    id text primary key,
    user_id text not null,
    data jsonb not null,
    created_at timestamptz not null default now(),
    quarantined_at timestamptz not null default now()
);

comment on table public.lookup_job_outcomes_legacy is
    'Pre-contract lookup outcome rows moved out of lookup_job_outcomes. Read-only history; nothing writes here after this migration.';

create index if not exists lookup_job_outcomes_legacy_user_lookup_idx
    on public.lookup_job_outcomes_legacy (user_id, (data->>'lookup_id'));

alter table public.lookup_job_outcomes_legacy enable row level security;

-- service_role exists on Supabase but not on a plain PostgreSQL host, where the
-- backend connects as owner and RLS is not the enforcement boundary. Guarded so
-- one migration file applies to both during the provider-neutral migration.
do $$
begin
    if exists (select 1 from pg_roles where rolname = 'service_role') then
        drop policy if exists lookup_job_outcomes_legacy_service_role_all
            on public.lookup_job_outcomes_legacy;
        create policy lookup_job_outcomes_legacy_service_role_all
            on public.lookup_job_outcomes_legacy
            for all
            to service_role
            using (true)
            with check (true);
    end if;
end
$$;

-- A row is current-contract only when it carries every required LookupAttemptOutcome
-- field. Note `failed`/`terminal` are computed properties, not stored fields, so
-- they must NOT be required here. Anything short predates the contract.
with legacy as (
    select id, user_id, data, created_at
    from public.lookup_job_outcomes
    where not (
        data ? 'id'
        and data ? 'user_id'
        and data ? 'lookup_id'
        and data ? 'job_id'
        and data ? 'pipeline_run_id'
        and data ? 'attempt'
        and data ? 'status'
        and data ? 'disposition'
        and data ? 'code'
        and data ? 'detail'
    )
)
insert into public.lookup_job_outcomes_legacy (id, user_id, data, created_at)
select id, user_id, data, created_at from legacy
on conflict (id) do nothing;

delete from public.lookup_job_outcomes
where id in (select id from public.lookup_job_outcomes_legacy);
