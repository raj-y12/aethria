-- =============================================================================
-- Add meta_churn_signals table
-- Used by meta/analyser.py _build_churn_signals() to read portfolio churn
-- signals written by FeedbackLoop. Follows the same doc-table pattern as
-- meta_scout_weights, meta_calibration_state, etc.
-- =============================================================================

create table if not exists public.meta_churn_signals (
  user_id text not null default 'default',
  key     text not null,
  data    jsonb not null default '{}',
  primary key (user_id, key)
);

create index if not exists meta_churn_signals_user_id_idx
  on public.meta_churn_signals (user_id);
