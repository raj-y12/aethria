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
  primary_thesis?: string;
  key_assumptions?: string[];
  biggest_unknown?: string;
  funding_stage?: string;
  location?: string;
  est_tam?: string;
  references?: string[];
  source_evidence?: Array<{
    reference: string;
    url?: string;
    supports?: string;
  }>;
  origin_type?: string;
  lookup_input_type?: string;
  /** Stable id from POST /api/startups/lookup for on-demand rows (matches pending UI state). */
  lookup_id?: string;
  lookup_query?: string;
  lookup_website?: string;
  /** Hash of the system prompt used by the Scout when this record was created. */
  prompt_version?: string;
  /** Per-field provenance tags from scout/reviewer enrichment. */
  field_provenance?: Record<string, string>;
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
  score_source?: string;
  improvement_to_9?: string[];
  market_reasoning?: string[];
  market_weaknesses?: string[];
  market_confidence?: 'low' | 'medium' | 'high';
  product_reasoning?: string[];
  product_weaknesses?: string[];
  product_confidence?: 'low' | 'medium' | 'high';
  technical_reasoning?: string[];
  technical_weaknesses?: string[];
  technical_confidence?: 'low' | 'medium' | 'high';
  execution_reasoning?: string[];
  execution_weaknesses?: string[];
  execution_confidence?: 'low' | 'medium' | 'high';
  defensibility_reasoning?: string[];
  defensibility_weaknesses?: string[];
  defensibility_confidence?: 'low' | 'medium' | 'high';
  /** Normalized extraction payload fed into deterministic scoring (audit trail). */
  structured_signals?: Record<string, unknown>;
}

/** Single synthesized view from persisted reviewer artifacts (template v1; no extra LLM). */
export interface AethriaView {
  headline: string;
  thesis_fit_line: string;
  tension_summary: string;
  focal_question: string;
}

export type ScoringDimensionKey =
  | 'market'
  | 'execution'
  | 'product'
  | 'technical'
  | 'defensibility';

export interface ScoringComponent {
  value?: string | null;
  label?: string | null;
  score: number;
  reasoning: string;
  evidence?: string | null;
  rule?: string | null;
  confidence?: number | null;
  /** True for judgment components with no objective anchor (P3.4): a qualitative 8 is
   *  not the same as an evidence-backed 8. Set by the backend scoring engine. */
  qualitative?: boolean | null;
}

export interface ScoringCriterion {
  score: number;
  confidence?: number | null;
  weight: number;
  evidence_status: 'complete' | 'partial' | 'missing' | string;
  missing_data_applied: boolean;
  reasoning: string;
  source_components: string[];
  name?: string | null;
  description?: string | null;
}

export interface ScoringDimension {
  score: number;
  /** True when the dimension has no supporting evidence: `score` is a placeholder and
   *  the dimension is excluded from the overall. Render as "Not scored", not a number. */
  unscored?: boolean | null;
  confidence?: number | null;
  components: Record<string, ScoringComponent>;
  criteria?: Record<string, ScoringCriterion>;
  /** Narrative bullets explaining the score; populated when no per-component breakdown is available. */
  reasoning?: string[] | null;
  /** Notable weaknesses surfaced by the reviewer for this dimension. */
  weaknesses?: string[] | null;
  /** Short qualitative label for the score (e.g. "Strong", "Concerning"). */
  score_label?: string | null;
}

export interface ScoreDispersion {
  /** Population standard deviation of the evidenced driver scores. */
  std: number;
  min: number;
  max: number;
  /** max − min, the most legible spread for a memo reader. */
  range: number;
}

export interface StructuredScoring {
  policy_version_id?: string | null;
  policy_hash?: string | null;
  market: ScoringDimension;
  execution: ScoringDimension;
  product: ScoringDimension;
  technical: ScoringDimension;
  defensibility: ScoringDimension;
  overall_score: number;
  overall_confidence?: number | null;
  /** Spread of the evidenced driver scores — distinguishes a flat 7 from a lopsided
   * [9,9,3,9] the headline average hides. Null when fewer than two drivers are scored. */
  overall_dispersion?: ScoreDispersion | null;
  /** Stage cohort the maturity-dependent criteria should be read against (P6.1). */
  stage_cohort?: string | null;
  stage_cohort_label?: string | null;
  /** Sector-relative TAM benchmark the Market score was graded on (P6.3). */
  sector_tam_benchmark?: string | null;
}

export interface PresentationComponent {
  id: string;
  label: string;
  score: number;
  band: string;
  has_evidence: boolean;
  interpretation: string;
}

export interface PresentationMissingEvidence {
  label: string;
  explanation: string;
}

export interface PresentationDimension {
  id: string;
  label: string;
  score: number;
  band: string;
  headline: string;
  score_interpretation: string;
  analyst_summary: string;
  /** Four-part analyst justification (replaces generic copy when present). */
  score_justification?: string;
  supports: string[];
  weakens: string[];
  missing_evidence: PresentationMissingEvidence[];
  diligence_actions: string[];
  confidence_label: string;
  confidence_tooltip: string;
  components: PresentationComponent[];
  consistency_status?: 'consistent' | 'mildly_inconsistent' | 'materially_inconsistent';
  consistency_explanation?: string;
  consistency_penalty?: number;
  positive_signal_strength?: number;
  positive_signal_count?: number;
  negative_signal_strength?: number;
  negative_signal_count?: number;
  evidence_coverage?: string;
  evidence_coverage_warning?: string;
  why_not_higher?: string[];
  implied_score_range?: [number, number];
  /** Soft, non-blocking analyst note when narrative and score may diverge. */
  analyst_review_note?: string;
}

export interface ScoringConsistencyAudit {
  overall_status: 'consistent' | 'mildly_inconsistent' | 'materially_inconsistent';
  review_notes?: string[];
}

export interface ScoringPresentation {
  overall_score: number;
  overall_band: string;
  confidence_label: string;
  confidence_tooltip: string;
  dimensions: PresentationDimension[];
  consistency_audit?: ScoringConsistencyAudit;
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
  /** Mean of core dimension scores (list view / blended reviewer output). */
  aggregate_score?: number | null;
  overall_score?: number | null;
  overall_label?: string | null;
  /** Rubric v1.1 band (Weak / Concerning / Promising / Strong); additive alongside legacy overall_label. */
  overall_rubric_band?: string | null;
  market_rubric_band?: string | null;
  product_rubric_band?: string | null;
  technical_rubric_band?: string | null;
  execution_rubric_band?: string | null;
  defensibility_rubric_band?: string | null;
  score_source?: string | null;
  improvement_to_9?: string[] | null;
  market_score_label?: string | null;
  product_score_label?: string | null;
  technical_score_label?: string | null;
  execution_score_label?: string | null;
  defensibility_score_label?: string | null;
  market_reasoning?: string[] | null;
  market_weaknesses?: string[] | null;
  market_confidence?: 'low' | 'medium' | 'high' | null;
  product_reasoning?: string[] | null;
  product_weaknesses?: string[] | null;
  product_confidence?: 'low' | 'medium' | 'high' | null;
  technical_reasoning?: string[] | null;
  technical_weaknesses?: string[] | null;
  technical_confidence?: 'low' | 'medium' | 'high' | null;
  execution_reasoning?: string[] | null;
  execution_weaknesses?: string[] | null;
  execution_confidence?: 'low' | 'medium' | 'high' | null;
  defensibility_reasoning?: string[] | null;
  defensibility_weaknesses?: string[] | null;
  defensibility_confidence?: 'low' | 'medium' | 'high' | null;
  /** Fund thesis alignment (reviewer / rule-based); surfaced in memo progressive load. */
  fund_thesis_version_id?: string | null;
  thesis_alignment_score?: number | null;
  thesis_matches_fund?: boolean | null;
  thesis_fit_points?: string[] | null;
  thesis_deviation_points?: string[] | null;
  thesis_alignment_confidence?: number | null;
  /** Resource policy thesis lens alignment (0–1); informational; does not drive rubric scores. */
  fund_thesis_alignment_score?: number | null;
  /** Structured explainable scoring payload returned by backend scoring engine. */
  scoring?: StructuredScoring | null;
  structured_scoring?: StructuredScoring | null;
  score_breakdown?: StructuredScoring | null;
  /** Investor-facing presentation DTO — the ONLY scoring data the UI should render. */
  scoring_presentation?: ScoringPresentation | null;
  market?: ScoringDimension | null;
  execution?: ScoringDimension | null;
  product?: ScoringDimension | null;
  technical?: ScoringDimension | null;
  defensibility?: ScoringDimension | null;
  /** Blended-score verdict from reviewer engine; preferred over raw verdict when present. */
  derived_verdict?: 'STRONG' | 'MEDIUM' | 'WEAK' | null;
  /** Primary-row normalized structured_signals (DefaultReviewer when available). */
  structured_signals?: Record<string, unknown>;
  resolution_notes?: string[] | null;
  disagreement_summary?: string | null;
  aethria_view?: AethriaView | null;
}

export interface PartnerSnapshot {
  one_liner: string;
  stage?: string | null;
  key_signal?: string | null;
}

export interface Partner {
  recommendation: 'INVEST' | 'PASS' | 'MONITOR';
  confidence?: number;            // 0.0–1.0
  thesis?: string;
  why_this_matters?: string;
  snapshot?: PartnerSnapshot;
  market_insight?: string;
  product_edge?: string;
  traction_signals?: string | null;
  risks?: string[];
  decision_rationale?: string;
  next_action?: string;
  next_step?: string;
  human_review_required?: boolean;
  /** When PartnerDecisionEngine fell back to LLM. */
  llm_fallback_reason?: string | null;
  /** Hash of the Partner agent prompt used when issuing this decision. */
  prompt_version?: string | null;
  /** Ordered narrative drivers for recommendation/rationale alignment (analytics/UI). */
  decision_drivers?: string[];
}

export interface Timestamps {
  discovered_at?: string;
  reviewed_at?: string;
  partnered_at?: string;
  unresolved_at?: string | null;
  first_seen_at?: string | null;
  last_seen_by_user_at?: string | null;
  acknowledged_at?: string | null;
}

export type RulingDecision = 'YES' | 'NO' | 'MAYBE';

export interface DecisionHistoryRecord {
  company_id: string;
  previous_decision?: RulingDecision | null;
  new_decision: RulingDecision;
  timestamp: string;
  rationale?: string | null;
  confidence?: number | null;
  score_snapshot?: Record<string, unknown> | null;
  risk_acknowledged?: boolean | null;
  config_version?: string | null;
  company_name?: string;
  sector?: string;
  funding_stage?: string | null;
}

export interface ConvictionState {
  current_ruling?: Record<string, unknown> | null;
  decision_history?: DecisionHistoryRecord[];
  ruling_rationale?: string | null;
  risk_acknowledgements?: Array<Record<string, unknown>>;
  score_changes?: Array<Record<string, unknown>>;
  confidence_changes?: Array<Record<string, unknown>>;
  escalation_events?: Array<Record<string, unknown>>;
}

/** Grounded financial facts. Every value is verified against a cited source by the
 *  backend grounding gate before it is stored — unverifiable figures are null and the
 *  matching *_missing flag is set. Never an estimate. */
export interface Financials {
  traction_metrics?: string | null;
  funding_history?: string | null;
  valuation_est?: string | null;
  ip_status?: string | null;
  revenue_missing?: boolean;
  funding_missing?: boolean;
  valuation_missing?: boolean;
}

export interface Startup {
  id: string;
  scout: Scout;
  review?: Review | null;
  partner?: Partner | null;
  financials?: Financials | null;
  /** Structured backend audit trail for Scout -> Reviewer -> Partner handoffs. */
  agent_trace?: Record<string, unknown> | null;
  timestamps?: Timestamps;
  /** Optional human override applied to a Partner decision (escalation resolution). */
  human_resolution?: {
    decision: RulingDecision;
    notes?: string;
    resolved_at?: string;
  } | null;
  conviction_state?: ConvictionState | null;
  unresolved_at?: string | null;
  is_new_to_user?: boolean;
  changed_since_last_visit?: boolean;
  queue_reason?: string | null;
  priority_reason?: string | null;
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
    decision?: RulingDecision;
    notes?: string;
    resolved_at?: string;
  } | null;
  conviction_state?: ConvictionState | null;
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
  entries?: {
    startup_id?: string;
    startup_name?: string;
    days_on_watchlist?: number;
    stale_warning?: boolean;
    signal_count?: number;
  }[];
}

export interface ConcentrationAnalytics {
  by_sector: Record<string, { count: number; pct_of_total: number }>;
  most_concentrated_sector: string;
  most_concentrated_theme: string;
  last_updated: string;
}

/** GET /api/analytics/system-health */
export interface SystemHealthSnapshot {
  calibration_warning: string | null;
  pending_escalations: number;
  queue_depths: {
    unreviewed: number;
    undecided: number;
    watchlist: number;
  };
  budget_status: Array<{
    agent_id: string;
    daily_calls_used: number;
    daily_calls_limit: number;
    daily_tokens_used: number;
    daily_tokens_limit: number;
    in_cooldown: boolean;
    cooldown_until: string | null;
  }>;
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

/** Analyst Invest/Pass/Monitor confirmations aggregated for meta-agent prompt proposals. */
export interface HumanFeedbackSummary {
  recent_count: number;
  by_outcome: { YES: number; NO: number; MAYBE: number };
  disagreed_with_ai_count: number;
  sample_notes: string[];
}

export interface MetaCycleReport {
  cycle_number: number;
  ran_at: string;
  next_cycle_at: string;
  mutations_applied: PromptMutationSummary[];
  /** Gated meta-agent prompt proposals (same items as mutations_applied when using new backend). */
  prompt_proposals?: PromptMutationSummary[];
  weight_updates: WeightUpdateSummary[];
  calibration_changes: CalibrationChangeSummary[];
  no_action_reasons: string[];
  /** Full analyser output from backend (optional on API). */
  signal_summary?: {
    human_feedback?: HumanFeedbackSummary;
  };
}

/** GET /api/meta/insights — curated summary from latest meta report */
export interface MetaInsightsPayload {
  latest: {
    cycle_number?: number;
    ran_at?: string;
    next_cycle_at?: string;
  } | null;
  what_changed: {
    mutations_applied?: unknown[];
    prompt_proposals?: unknown[];
    weight_updates?: unknown[];
    calibration_changes?: unknown[];
  } | null;
  why: string[];
  signal_summary?: MetaCycleReport['signal_summary'];
}

export interface MetaPromptLibraryEntrySummary {
  library_key: string;
  created_at?: string;
  cycle_number?: number;
  reasoning?: string;
  promotion_status?: string;
  previous_hash?: string;
  prompt_char_count?: number;
  prompt?: string;
  warning?: string;
  error?: string;
}

export interface MetaPromptState {
  active: Record<string, string>;
  active_detail: Record<string, MetaPromptLibraryEntrySummary>;
  pending: MetaPromptLibraryEntrySummary[];
  restart_note?: string;
}

export interface MetaEvalSet {
  startup_ids: string[];
  count: number;
  max: number;
}

export interface PromptEvaluateRow {
  startup_id: string;
  status: string;
  baseline_verdict?: string;
  candidate_verdict?: string;
  verdict_match?: boolean;
  regression?: boolean;
  mean_abs_delta?: number;
  error?: string;
}

export interface PromptEvaluateSummary {
  n_requested: number;
  n_compared: number;
  regression_count: number;
  verdict_agreements: number;
  mean_abs_score_delta: number;
  passed: boolean;
  pass_reason: string;
  evaluated_at: string;
}

export interface PromptEvaluateResult {
  ok: boolean;
  error?: string;
  library_key?: string;
  agent_target?: string;
  truncated?: boolean;
  max_startups?: number;
  summary?: PromptEvaluateSummary;
  rows?: PromptEvaluateRow[];
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
