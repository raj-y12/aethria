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
  prompt_version?: string;
}

export interface SingleReview {
  reviewer_type: string;
  market_score: number;
  product_score: number;
  technical_score: number;
  execution_score: number;
  defensibility_score?: number;
  verdict: string;
  overall_summary: string;
  key_risks: string[];
  prompt_version?: string;
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
  score_reasoning?: Record<string, string>;
  diligence_red_flags?: string[];
  assumption_feedback?: string[];
  team_analysis?: string[];
  competition_analysis?: string[];
  business_model_analysis?: string[];
  investment_thesis?: string[];
  risk_mitigation?: string[];
  prompt_version?: string;
  reviews?: SingleReview[];
  consensus_verdict?: string;
  reviewer_disagreement?: boolean;
  score_variance?: Record<string, number>;
}

export interface Partner {
  decision: 'YES' | 'NO' | 'MAYBE' | 'PASS' | 'WATCH';
  confidence?: number;
  rationale?: string;
  next_action?: string;
  next_step?: string;
  human_review_required?: boolean;
  llm_fallback_reason?: string | null;
  memo_at_decision?: string | null;
  portfolio_context_at_decision?: {
    sector_counts: Record<string, number>;
    stage_counts: Record<string, number>;
    total_portfolio_size: number;
  } | null;
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
  human_resolution?: {
    decision: string;
    notes: string;
    resolved_at: string;
  } | null;
}

export interface EscalationItem {
  id: string;
  scout: Scout;
  review?: Review | null;
  partner?: Partner | null;
  timestamps?: Timestamps;
  human_resolution?: {
    decision: string;
    notes: string;
    resolved_at: string;
  } | null;
}

export interface SignalItem {
  id: string;
  startup_id: string;
  signal_type: string;
  strength: number;
  description: string;
  detected_at: string;
  source?: string;
  tracker_agent_id?: string;
}

export interface RejectionAnalytics {
  most_common_red_flags: { flag: string; count: number }[];
  rejection_by_sector: Record<string, number>;
  avg_scores_at_rejection: Record<string, number>;
  most_common_fail_dimensions: { dimension: string; count: number }[];
}

export interface WatchlistAnalytics {
  total: number;
  stale: number;
  avg_days: number;
}

export interface ConcentrationAnalytics {
  by_sector: Record<string, {
    count: number;
    pct_of_total: number;
    avg_confidence: number;
    avg_review_score: number | null;
  }>;
  most_concentrated_sector: string;
  most_concentrated_theme: string;
  last_updated: string;
}

export interface MetaCycleReport {
  cycle_number: number;
  ran_at: string;
  signal_summary: Record<string, unknown>;
  mutations_applied: {
    agent_target: string;
    reasoning: string;
    previous_prompt_hash: string;
    new_prompt_hash: string;
  }[];
  weight_updates: {
    scout_type: string;
    previous_weight: number;
    new_weight: number;
    reasoning: string;
  }[];
  calibration_changes: {
    parameter: string;
    previous_value: number;
    new_value: number;
    direction: string;
    reasoning: string;
  }[];
  no_action_reasons: string[];
  next_cycle_at: string;
}

export interface ScoutWeights {
  MarketDrivenScout: number;
  BuilderTechnicalScout: number;
  PainPointScout: number;
  ContrarianScout: number;
}

export interface CalibrationState {
  confidence_threshold_override: number | null;
  reviewer_weak_threshold_override: number | null;
  reviewer_strong_threshold_override: number | null;
  last_calibrated_at: string | null;
  last_calibrated_cycle: number;
  calibration_history: {
    parameter: string;
    direction: string;
    applied_at: string;
    reasoning: string;
  }[];
}
