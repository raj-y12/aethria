-- =============================================================================
-- Company Resolver: resolution_status list projection
-- =============================================================================
-- Stage-1 lookup resolution outcome (FOUND | PARTIAL | LOW_CONFIDENCE |
-- NEEDS_REVIEW | NOT_FOUND) stored on scout_info by the Company Resolver.
-- Projected so the deal-flow list can badge weak/needs-review lookups without
-- fetching the full scout blob.
-- Idempotent: safe to re-run if column already exists.
-- =============================================================================

alter table public.startups
  add column if not exists list_resolution_status text
    generated always as (nullif(trim(scout_info->>'resolution_status'), '')) stored;
