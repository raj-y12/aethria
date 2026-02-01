# STEP 1: Code Analysis (VC Pipeline Upgrade)

**Purpose:** Document existing Reviewer, Partner, Memo, and schema before adding VC best-practice fields. No functionality removed; add-only.

---

## Reviewer LLM (`backend/reviewer/base.py`)

**Existing:**
- System prompt built from `reviewer_rules.json` + `evaluation_rubric_v1.json` (red flags block, conservative tone, hypothesis-driven evaluation).
- User prompt: Scout text (name, one_line, sector, problem, solution, target_users, why_now, confidence; optional primary_thesis, key_assumptions, biggest_unknown) + JSON schema.
- **Output schema (in prompt):** market_score, product_score, technical_score, execution_score, defensibility_score, overall_summary, key_risks, verdict, diligence_red_flags, assumption_feedback.
- Post-parse defaults: defensibility_score=None, diligence_red_flags=[], assumption_feedback=[].
- No narrative “link score to reasoning” instruction; no team_analysis, competition_analysis, business_model_analysis, investment_thesis, risk_mitigation.

**Preserved:** All existing prompt text and schema; add new optional fields and narrative guidance.

---

## Reviewer schema (`backend/reviewer/schema.py`)

**Existing:**
- **Required:** market_score, product_score, technical_score, execution_score, overall_summary, key_risks, verdict (validated types and 1–10 / STRONG|MEDIUM|WEAK).
- **Optional:** defensibility_score (1–10), diligence_red_flags (list[str]), assumption_feedback (list[str]), reviewer_agent_id.
- `validate_reviewer_output()` enforces required, scores 1–10, verdict enum, list-of-strings for key_risks, diligence_red_flags, assumption_feedback.

**Preserved:** All required and existing optional validation. Add optional team_analysis, competition_analysis, business_model_analysis, investment_thesis, risk_mitigation (list[str]).

---

## Partner decision (`backend/partner/decision.py`)

**Existing:**
- Inputs: verdict, market/product/technical/execution, key_risks, assumption_feedback; avg_score = mean of 4 scores; assumption_risks from _compute_assumption_risks; conviction_adjust = -1 if assumption_risks else 0.
- Rules (order): 1) WEAK→NO; 2) critical_risk→NO; 3) avg < 6→NO; 4) STRONG + avg ≥ 8→YES (human_review_required=True, has_red_flags→request_cap_table_and_review); 5) MEDIUM + avg ≥ 7→MAYBE or LLM if contradiction/missing_assumptions; 6) MEDIUM + 6≤avg<7→LLM or NO; 7) default NO.
- LLM fallback: contradictory scores (gap ≥ 4 or high/low threshold), missing_assumptions_affecting_decision, medium_borderline_avg.
- **Not used today:** team_analysis, business_model_analysis, risk_mitigation.

**Preserved:** All rules and thresholds. Add: read team_analysis, business_model_analysis; _has_missing_team, _has_missing_business_model; human_review when STRONG+YES but missing team/business model; conviction +/- for team/business model quality; optional LLM trigger for missing critical qualitative info.

---

## Partner rules (`resources/partner_rules.json`)

**Existing:** verdict_rules, score_thresholds, critical_risk_keywords, contradictory_scores, red_flag_keywords, next_actions, llm_fallback_triggers, assumption_risk_keywords. No qualitative keys.

**Preserved:** No removal. Optional: add keys for conviction_boost_team / conviction_penalty_missing_team (used in code with defaults).

---

## MemoGenerator (`backend/memo_generator.py`)

**Existing sections (order):** Header, Company Overview, Problem & Opportunity, Financials & Traction, Reviewer Analysis (Scores, Verdict, Overall Summary, Key Risks, Diligence Red Flags), Partner Decision, Next Steps. Uses [MISSING] for funding_stage, est_tam, traction_metrics, funding_history, valuation_est, ip_status.

**Preserved:** All existing sections and content. Add: Team & Founders (team_analysis), Competition & Market Position (competition_analysis), Business Model & Monetization (business_model_analysis), Investment Thesis (investment_thesis), Risk Mitigation (risk_mitigation), Deal Structure & Cap Table (financials + placeholder), Exit Scenarios (placeholder). Use [MISSING] when lists missing or empty.

---

## Memo template (`resources/memos/investment_memo_v1.json`)

**Existing:** sections: header, company_overview, problem_opportunity, financials_traction, reviewer_analysis, partner_decision, next_steps; missing_value "[MISSING]", tone analyst.

**Preserved:** All existing section ids and order. Add new section ids for new memo sections (for reference; MemoGenerator drives actual order).

---

## Models (`backend/models.py`)

**ReviewInfo existing:** market_score, product_score, technical_score, execution_score, defensibility_score, overall_summary, key_risks, verdict, diligence_red_flags, reviewer_agent_id, reviewed_at. **Note:** assumption_feedback is not on ReviewInfo today; partner/engine uses getattr(review_info, "assumption_feedback", []).

**Preserved:** All existing fields. Add: assumption_feedback (List[str], default []), team_analysis, competition_analysis, business_model_analysis, investment_thesis, risk_mitigation (Optional[List[str]] = None) so storage and memo can persist/display them.

---

## Adapters (`backend/adapters.py`)

**reviewer_output_to_review_info:** Maps market_score, product_score, technical_score, execution_score, defensibility_score, overall_summary, key_risks, verdict, diligence_red_flags, reviewer_agent_id. Does not map assumption_feedback or new qualitative fields.

**Preserved:** All current mappings. Add: assumption_feedback, team_analysis, competition_analysis, business_model_analysis, investment_thesis, risk_mitigation from reviewer_output with safe defaults ([] or None).

---

## Backward compatibility

- Reviewer: New fields optional; LLM can omit them; validator allows omission; base.py defaults new list fields to [] after parse.
- Partner: New logic only adds conditions (e.g. human_review when missing team); existing thresholds unchanged.
- Memo: New sections only appended or inserted; existing sections unchanged; getattr or optional chaining for new fields.
- Models/Storage: New ReviewInfo fields optional; from_dict/to_dict will round-trip; existing JSON without these keys still loads (Pydantic default).
