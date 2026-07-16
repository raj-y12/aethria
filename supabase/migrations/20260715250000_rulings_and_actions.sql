-- Phase 5: append-only GP rulings, attributed overrides, and approval-gated actions.

create table if not exists public.human_rulings (
  ruling_id uuid primary key default gen_random_uuid(),
  user_id text not null,
  opportunity_id uuid not null,
  recommendation_id uuid,
  decision text not null check (decision in ('advance','monitor','pass','invest')),
  rationale text not null,
  risk_acknowledgement text,
  mandate_exception text,
  investor_confidence double precision not null check (investor_confidence between 0 and 1),
  actor_id text not null,
  prior_ruling_id uuid,
  created_at timestamptz not null default now(),
  unique (user_id, ruling_id),
  foreign key (user_id, opportunity_id) references public.opportunities (user_id, opportunity_id),
  foreign key (user_id, recommendation_id) references public.recommendations (user_id, recommendation_id),
  foreign key (user_id, prior_ruling_id) references public.human_rulings (user_id, ruling_id)
);
create index if not exists human_rulings_opportunity_idx on public.human_rulings (user_id, opportunity_id, created_at desc);

create table if not exists public.override_signals (
  override_signal_id uuid primary key default gen_random_uuid(),
  user_id text not null,
  opportunity_id uuid not null,
  ruling_id uuid not null,
  recommendation_id uuid,
  recommendation_state text,
  ruling_decision text not null,
  override_type text not null check (override_type in ('evidence_correction','missing_private_evidence','policy_disagreement','founder_judgment','market_judgment','timing','strategic_exception','relationship_context','confidence_disagreement')),
  note text,
  created_at timestamptz not null default now(),
  unique (user_id, override_signal_id),
  unique (user_id, ruling_id),
  foreign key (user_id, opportunity_id) references public.opportunities (user_id, opportunity_id),
  foreign key (user_id, ruling_id) references public.human_rulings (user_id, ruling_id),
  foreign key (user_id, recommendation_id) references public.recommendations (user_id, recommendation_id)
);

create table if not exists public.workflow_actions (
  workflow_action_id uuid primary key default gen_random_uuid(),
  user_id text not null,
  opportunity_id uuid not null,
  action_type text not null check (action_type in ('prepare_diligence_questions','draft_information_request','refresh_evidence','schedule_monitor_review','export_to_crm','generate_decision_pack','resolve_identity')),
  trigger_type text not null,
  trigger_id uuid,
  status text not null check (status in ('draft','pending_approval','approved','running','completed','failed','cancelled')),
  generated_content jsonb not null default '{}'::jsonb,
  approved_content jsonb,
  missing_evidence jsonb not null default '[]'::jsonb,
  requires_approval boolean not null default false,
  due_at timestamptz,
  completed_at timestamptz,
  external_destination text,
  external_reference text,
  approved_by text,
  approved_at timestamptz,
  failure_code text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id, workflow_action_id),
  foreign key (user_id, opportunity_id) references public.opportunities (user_id, opportunity_id)
);
create index if not exists workflow_actions_queue_idx on public.workflow_actions (user_id, status, due_at, created_at);

do $$
begin
  if not exists (select 1 from pg_constraint where conname = 'opportunities_current_ruling_fk') then
    alter table public.opportunities add constraint opportunities_current_ruling_fk
      foreign key (user_id, current_ruling_id)
      references public.human_rulings (user_id, ruling_id);
  end if;
end $$;

create or replace function public.prevent_ruling_mutation()
returns trigger language plpgsql security invoker set search_path=public as $$
begin
  raise exception 'human rulings and override signals are append-only';
end;
$$;
create trigger human_rulings_append_only before update or delete on public.human_rulings
for each row execute function public.prevent_ruling_mutation();
create trigger override_signals_append_only before update or delete on public.override_signals
for each row execute function public.prevent_ruling_mutation();

alter table public.human_rulings enable row level security;
alter table public.override_signals enable row level security;
alter table public.workflow_actions enable row level security;
create policy human_rulings_service_role_all on public.human_rulings for all to service_role using (true) with check (true);
create policy override_signals_service_role_all on public.override_signals for all to service_role using (true) with check (true);
create policy workflow_actions_service_role_all on public.workflow_actions for all to service_role using (true) with check (true);
revoke all on table public.human_rulings, public.override_signals, public.workflow_actions from anon, authenticated;
grant select, insert, update, delete on table public.human_rulings, public.override_signals, public.workflow_actions to service_role;
revoke all on function public.prevent_ruling_mutation() from public;
grant execute on function public.prevent_ruling_mutation() to service_role;
