-- Separate post-diligence investment transitions from the three-way opportunity disposition.
-- Historical INVEST rulings remain readable; new API writes use ruling_context to distinguish them.

alter table public.human_rulings
  add column if not exists ruling_context text not null default 'disposition';

do $$
begin
  if not exists (select 1 from pg_constraint where conname = 'human_rulings_context_check') then
    alter table public.human_rulings add constraint human_rulings_context_check
      check (ruling_context in ('disposition', 'investment_transition'));
  end if;
end $$;

create index if not exists human_rulings_investment_transition_idx
  on public.human_rulings (user_id, opportunity_id, created_at desc)
  where ruling_context = 'investment_transition';

comment on column public.human_rulings.ruling_context is
  'disposition for Advance/Monitor/Pass; investment_transition for explicit post-diligence Invest. Historical Invest rows remain compatible.';
