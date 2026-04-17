-- =============================================================================
-- Fix partner_decision generated column to read 'recommendation' (new schema)
-- with fallback to 'decision' (legacy schema) for backward compatibility.
-- =============================================================================
-- Old column read partner_info->>'decision' (YES/NO/MAYBE).
-- New PartnerInfo schema uses 'recommendation' (INVEST/PASS/MONITOR).
-- coalesce ensures both old and new records resolve correctly.
-- =============================================================================

alter table public.startups
  drop column if exists partner_decision;

alter table public.startups
  add column partner_decision text
    generated always as (
      nullif(trim(coalesce(
        nullif(trim(partner_info->>'recommendation'), ''),
        nullif(trim(partner_info->>'decision'), '')
      )), '')
    ) stored;
