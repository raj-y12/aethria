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
}

export interface Partner {
  decision: 'YES' | 'NO' | 'MAYBE' | 'PASS' | 'WATCH';
  confidence?: number;
  rationale?: string;
  next_action?: string;
  next_step?: string;
  human_review_required?: boolean;
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
}
