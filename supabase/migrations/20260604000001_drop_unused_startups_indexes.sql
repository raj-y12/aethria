-- Drop unused GIN indexes and one duplicate btree index on public.startups.
--
-- Rationale (Supabase performance advisor + pg_stat_user_indexes):
--   * These indexes have zero recorded scans.
--   * The GIN indexes sit on the large JSONB columns and are re-maintained on
--     every startup row write. The pipeline rewrites startup rows frequently
--     (scout -> review -> partner -> meta), so these indexes cause heavy write
--     amplification (HOT-update ratio on startups was ~2%) for no read benefit.
--     No query uses JSONB containment; list reads use the generated columns
--     (display_name, list_*, partner_decision, partner_human_review_required).
--
-- Safety: dropping an index never changes stored data or query *results* — only
-- write cost and disk. None of these are PK/unique constraints. Reversible by
-- recreating the index. Uses IF EXISTS so re-application is a no-op.

-- Unused JSONB GIN indexes.
DROP INDEX IF EXISTS public.startups_scout_info_gin_idx;
DROP INDEX IF EXISTS public.startups_review_info_gin_idx;
DROP INDEX IF EXISTS public.startups_partner_info_gin_idx;
DROP INDEX IF EXISTS public.startups_conviction_state_gin_idx;
DROP INDEX IF EXISTS public.startups_user_agent_trace_gin_idx;

-- Exact duplicate of startups_user_unresolved_idx
-- (both: btree (user_id, unresolved_at DESC) WHERE unresolved_at IS NOT NULL).
-- Keep startups_user_unresolved_idx; drop the redundant copy.
DROP INDEX IF EXISTS public.startups_user_queue_stale_idx;
