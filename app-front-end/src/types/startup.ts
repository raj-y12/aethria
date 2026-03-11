export interface Scout {
  id: string;
  scout_type: string;
  name: string;
  one_line: string;
  sector: string;
  problem?: string;
  solution?: string;
  target_users?: string;
  why_now: string;
  confidence: number;
  funding_stage?: string;
  est_tam?: string;
  references?: string[];
  /** Hash of the system prompt used by the Scout when this record was created. */
  prompt_version?: string;
}

export interface SingleReview {
  reviewer_type: 'DefaultReviewer' | 'SkepticalReviewer' | 'OpportunistReviewer';
  market_score: number;
  product_score: number;
  technical_score: number;
  execution_score: number;
  defensibility_score: number;
  verdict: 'STRONG' | 'MEDIUM' | 'WEAK';
  overall_summary: string;
  key_risks: string[];
  prompt_version: string;
}

export interface Review {
  market_score?: number;
  product_score?: number;
  technical_score?: number;
  execution_score?: number;
  defensibility_score?: number;
  overall_summary?: string;
  key_risks?: string[];
  verdict?: string;
  /** Per-dimension reasoning, e.g. { market_score: "...", product_score: "..." } */
  score_reasoning?: Record<string, string>;
  diligence_red_flags?: string[];
  assumption_feedback?: string[];
  team_analysis?: string[];
  competition_analysis?: string[];
  business_model_analysis?: string[];
  investment_thesis?: string[];
  risk_mitigation?: string[];
  /**
   * Detailed per-reviewer breakdown when multiple reviewers run on the same startup.
   * When present, these are used for the "Reviewer divergence" table in the memo.
   */
  reviews?: SingleReview[];
  /** Consensus verdict derived from individual reviewers. */
  consensus_verdict?: 'STRONG' | 'MEDIUM' | 'WEAK';
  /**
   * True when multiple reviewers disagree; used for contested badge in grid and
   * to drive the divergence section in the memo.
   */
  reviewer_disagreement?: boolean;
  /** Per-dimension score variance (standard deviation) across reviewers. */
  score_variance?: Record<string, number>;
}

export interface Partner {
  decision: 'YES' | 'NO' | 'MAYBE' | 'PASS' | 'WATCH';
  confidence?: number;
  rationale?: string;
  next_action?: string;
  next_step?: string;
  human_review_required?: boolean;
  /** When PartnerDecisionEngine fell back to LLM. */
  llm_fallback_reason?: string | null;
  /** Frozen memo snapshot taken at the time of decision, when available. */
  memo_at_decision?: string | null;
  /**
   * Snapshot of portfolio composition at decision time, used to explain
   * diversification / concentration trade-offs in memos.
   */
  portfolio_context_at_decision?: {
    sector_counts: Record<string, number>;
    stage_counts: Record<string, number>;
    total_portfolio_size: number;
  } | null;
  /** Hash of the Partner agent prompt used when issuing this decision. */
  prompt_version?: string | null;
}

export interface Timestamps {
  discovered_at?: string;
  reviewed_at?: string;
  partnered_at?: string;
}

export interface Startup {
  id: string;
  scout: Scout;
  review?: Review | null;
  partner?: Partner | null;
  timestamps?: Timestamps;
  /** Optional human override applied to a Partner decision (escalation resolution). */
  human_resolution?: {
    decision: 'YES' | 'NO' | 'MAYBE';
    notes?: string;
    resolved_at?: string;
  } | null;
}

// ─── System Intelligence / Meta-Agent Types ───────────────────────────────────

export interface SignalItem {
  id?: string;
  startup_id?: string;
  signal_type: string;
  description?: string;
  strength?: number;
  detected_at?: string;
  tracker_agent_id?: string;
  source?: string;
  affected_confidence?: number | null;
}

export interface EscalationItem {
  id: string;
  startup_id?: string;
  startup_name?: string;
  scout?: Scout;
  review?: Review | null;
  partner?: Partner | null;
  created_at?: string;
  human_resolution?: {
    decision?: 'YES' | 'NO' | 'MAYBE';
    notes?: string;
    resolved_at?: string;
  } | null;
}

export interface RejectionAnalytics {
  most_common_red_flags: { flag: string; count: number }[];
  rejection_by_sector: Record<string, { count: number; pct_of_total: number }>;
  avg_scores_at_rejection: Record<string, number>;
  most_common_fail_dimensions: string[];
}

export interface WatchlistAnalytics {
  total: number;
  stale: number;
  avg_days: number;
}

export interface ConcentrationAnalytics {
  by_sector: Record<string, { count: number; pct_of_total: number }>;
  most_concentrated_sector: string;
  most_concentrated_theme: string;
  last_updated: string;
}

export interface PromptMutationSummary {
  agent_target: string;
  reasoning: string;
  previous_prompt_hash: string;
  new_prompt_hash: string;
}

export interface WeightUpdateSummary {
  agent_target: string;
  previous_weight: number;
  new_weight: number;
}

export interface CalibrationChangeSummary {
  parameter: string;
  previous_value: number | null;
  new_value: number | null;
  direction?: 'tightened' | 'loosened' | 'unchanged' | string;
  reasoning: string;
}

export interface MetaCycleReport {
  cycle_number: number;
  ran_at: string;
  next_cycle_at: string;
  mutations_applied: PromptMutationSummary[];
  weight_updates: WeightUpdateSummary[];
  calibration_changes: CalibrationChangeSummary[];
  no_action_reasons: string[];
}

export interface ScoutWeights {
  MarketDrivenScout: number;
  BuilderTechnicalScout: number;
  PainPointScout: number;
  ContrarianScout: number;
  // Allow any future agents without breaking types:
  [agentName: string]: number;
}

export interface CalibrationHistoryEntry {
  parameter: string;
  direction: 'tightened' | 'loosened' | 'unchanged' | string;
  reasoning: string;
  applied_at?: string;
}

export interface CalibrationState {
  confidence_threshold_override: number | null;
  reviewer_weak_threshold_override: number | null;
  reviewer_strong_threshold_override: number | null;
  last_calibrated_at: string | null;
  last_calibrated_cycle: number;
  calibration_history: CalibrationHistoryEntry[];
}
