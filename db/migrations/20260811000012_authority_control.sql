-- Provider-neutral authority rollout and canonical workflow contract.
alter table public.opportunities
  add column if not exists workflow_state text not null default 'admitted',
  add column if not exists workflow_version integer not null default 0,
  add column if not exists block_code text,
  add column if not exists block_detail text,
  add column if not exists block_recovery text,
  add column if not exists last_transition_id uuid;

alter table public.opportunities
  drop constraint if exists opportunities_workflow_state_check,
  add constraint opportunities_workflow_state_check check (workflow_state in (
    'admitted','identity_review','triage_pending','triaged_light','deep_review_pending',
    'evidence_active','evaluation_pending','ruling_pending','monitoring','completed',
    'blocked','archived'
  )),
  drop constraint if exists opportunities_workflow_version_check,
  add constraint opportunities_workflow_version_check check (workflow_version >= 0),
  drop constraint if exists opportunities_workflow_block_check,
  add constraint opportunities_workflow_block_check check (
    workflow_state <> 'blocked' or (block_code is not null and block_detail is not null and block_recovery is not null)
  ),
  drop constraint if exists opportunities_workflow_block_code_check,
  add constraint opportunities_workflow_block_code_check check (
    block_code is null or block_code in (
      'identity_review_required','thesis_required','policy_required','evidence_required',
      'evaluation_required','ruling_required','reconciliation_required','kill_switch_active'
    )
  );
create index if not exists opportunities_tenant_workflow_state_idx
  on public.opportunities (user_id, workflow_state, updated_at desc);

create table if not exists public.tenant_authority_rollouts (
  user_id text primary key,
  mode text not null check (mode in ('legacy','shadow','backfill','canonical_write','canonical_read')),
  version integer not null default 0 check (version >= 0),
  activated_at timestamptz,
  activated_by text,
  snapshot_id text,
  last_reconciliation_status text,
  kill_switch boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists tenant_authority_rollouts_tenant_mode_idx
  on public.tenant_authority_rollouts (user_id, mode);

create table if not exists public.authority_projection_receipts (
  receipt_id uuid primary key default gen_random_uuid(),
  user_id text not null,
  event_id uuid not null,
  consumer text not null check (length(btrim(consumer)) > 0),
  aggregate_type text not null check (length(btrim(aggregate_type)) > 0),
  aggregate_id uuid not null,
  applied_at timestamptz not null default now(),
  projection_hash text,
  unique (user_id, event_id, consumer)
);
create index if not exists authority_projection_receipts_aggregate_idx
  on public.authority_projection_receipts (user_id, aggregate_type, aggregate_id, applied_at desc);

create or replace function public.touch_authority_rollout_updated_at()
returns trigger language plpgsql security invoker set search_path = public as $$
begin new.updated_at = now(); return new; end;
$$;
drop trigger if exists tenant_authority_rollouts_touch_updated_at on public.tenant_authority_rollouts;
create trigger tenant_authority_rollouts_touch_updated_at
before update on public.tenant_authority_rollouts
for each row execute function public.touch_authority_rollout_updated_at();
