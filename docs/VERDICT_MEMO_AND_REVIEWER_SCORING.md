# Verdict, Investment Memo, and Reviewer Scoring

This document explains how the **Reviewer verdict** is determined, how the **Partner investment decision** is made, how the **Investment Memo** is produced, and on what **metrics the Reviewer** scores each startup.

---

## 1. How the Reviewer Verdict Is Decided

The **verdict** is one of `STRONG`, `MEDIUM`, or `WEAK`. It is **produced by the Reviewer LLM** for each Scout discovery; it is not computed deterministically from scores in code.

### Who decides it

- The **Reviewer** (`backend/reviewer/base.py`) is an LLM-based agent. For each startup it:
  - Receives Scout output (company name, one-line, sector, problem, solution, target users, why now, confidence, and optional hypothesis fields: `primary_thesis`, `key_assumptions`, `biggest_unknown`).
  - Is given a system prompt built from **reviewer rules** and the **evaluation rubric** (`resources/reviewer_rules.json`, `resources/rubrics/evaluation_rubric_v1.json`).
  - Is asked to output strict JSON that includes the five dimension scores (see below) **and** `verdict`.

So the **verdict is chosen by the model** in one shot, guided by the rubric’s thresholds and the same criteria used for the scores.

### Guidance the LLM gets (rubric thresholds)

The rubric defines **verdict thresholds** that the LLM is expected to align with:

| Verdict | min_avg | min_any | max_low |
|--------|---------|---------|--------|
| **STRONG** | 8.0     | 7       | 0      |
| **MEDIUM** | 6.0     | 5       | 1      |
| **WEAK**   | 0       | 0       | 999    |

- **STRONG**: Average of dimension scores ≥ 8.0, no dimension below 7, no “low” band (1–4) allowed.
- **MEDIUM**: Average ≥ 6.0, at least one dimension ≥ 5, at most one dimension in the low range.
- **WEAK**: Anything else (e.g. low average or multiple low scores).

The Reviewer is instructed to be conservative; most ideas should land in the 4–7 range, and only exceptional ones in 8+.

### Output and validation

The Reviewer’s JSON is validated by `validate_reviewer_output()` in `backend/reviewer/schema.py`. `verdict` must be exactly one of `"STRONG"`, `"MEDIUM"`, `"WEAK"`.

---

## 2. Reviewer Scoring Metrics (Dimensions)

The Reviewer scores each startup on **five dimensions**, each from **1 to 10**. Definitions come from `resources/rubrics/evaluation_rubric_v1.json`.

### Required dimensions (always in Reviewer output)

| Dimension ID           | Name        | What it measures |
|-----------------------|------------|-------------------|
| **market_score**      | Market     | Size, growth, timing, and accessibility of the market. |
| **product_score**     | Product    | Clarity of problem, fit of solution, and differentiation. |
| **technical_score**   | Technical  | Feasibility, complexity, moat, and execution risk. |
| **execution_score**   | Execution  | Team, go-to-market, competition, and path to scale. |

### Optional dimension

| Dimension ID              | Name          | What it measures |
|---------------------------|---------------|-------------------|
| **defensibility_score**   | Defensibility | Moat from solution: tech, network, data, regulation, switching cost. |

### Score bands (from rubric)

For each dimension the rubric defines:

- **High (8–10)**: e.g. large addressable market, clear problem–solution fit, feasible tech with moat, credible team/GTM, or clear defensibility.
- **Mid (5–7)**: e.g. moderate or unproven market, reasonable but undifferentiated product, feasible but with execution risk, some differentiation but replicable.
- **Low (1–4)**: e.g. small/unproven market, solution in search of problem, unproven tech or commodity, team/GTM mismatch or implausible path, no moat.

The system prompt in `reviewer/base.py` tells the Reviewer to evaluate:

- **Market**: opportunity size, timing, trends.
- **Product**: feasibility, design, UX.
- **Technical**: complexity, moats, scalability.
- **Execution**: team, GTM, competition.
- **Defensibility**: technical moats, network effects, regulatory barriers, switching costs, brand/trust.

### Red flags (diligence)

The Reviewer is also instructed to output **diligence_red_flags** using only labels from the rubric / reviewer rules, for example:

- Missing founding team details  
- Missing revenue or traction data  
- Competitive landscape unclear  
- Missing valuation data  
- Regulatory or execution impossibility  
- Gap ≥ 4 between highest and lowest dimension (contradictory scores)

These do not change the numeric scores or verdict directly but are used later by the Partner and in the memo.

### Hypothesis-driven evaluation

When Scout output includes `primary_thesis`, `key_assumptions`, and `biggest_unknown`, the Reviewer must:

- Comment on those assumptions in **assumption_feedback**.
- Highlight critical unknowns that could invalidate the thesis.
- Not invent missing data.

---

## 3. How the Partner Investment Decision Is Made

The **Partner** (`backend/partner/decision.py`) does **not** use an LLM by default. It takes the **Reviewer’s verdict and scores** (and other outputs) and applies **rule-based logic** from `resources/partner_rules.json` to produce a **decision**: `YES`, `MAYBE`, or `NO`.

### Inputs used

- **From Reviewer**: `verdict`, `market_score`, `product_score`, `technical_score`, `execution_score`, `key_risks`, `assumption_feedback`.
- **Average score**: `avg_score = (market + product + technical + execution) / 4`. Defensibility is **not** included in this average.
- **Derived**: `assumption_risks` (from assumption_feedback + Scout hypothesis), `has_critical_risk`, `has_red_flags`, `has_contradictory_scores`, `has_missing_assumptions_affecting_decision` (from rules/keywords).

### Decision rules (priority order)

1. **WEAK verdict → NO**  
   Conviction 9, rationale references low quality / crowded market.

2. **Critical risks → NO**  
   If `key_risks` contain regulatory/execution-impossibility keywords (from `partner_rules.json`). Conviction 8 (or 7 if assumption_risks).

3. **Average score &lt; 6.0 → NO**  
   Regardless of verdict. Conviction 7 (or 6 with assumption_risks).

4. **STRONG verdict and avg_score ≥ 8.0 → YES**  
   Conviction 8 (or 7 with assumption_risks). Next action: “Request Cap Table” or “Request Cap Table + Technical Code Review” if red flags. `human_review_required: true`.

5. **MEDIUM verdict and avg_score ≥ 7.0 → MAYBE**  
   Unless LLM fallback is triggered (contradictory scores or assumption_risks). Conviction 6 (or 5 with assumption_risks). Next action: e.g. “Monitor market and track progress”.

6. **MEDIUM verdict and 6.0 ≤ avg_score &lt; 7.0 (borderline) → LLM fallback or NO**  
   If LLM fallback is enabled and triggered: MAYBE with human review. Otherwise: NO with conviction 5 (or 4 with assumption_risks).

7. **Default → NO**  
   Conviction 6 (or 5 with assumption_risks).

### Score thresholds (from partner_rules.json)

- `min_avg_pass`: 6.0  
- `min_avg_strong_yes`: 8.0  
- `min_avg_medium_maybe`: 7.0  
- `min_avg_borderline_low` / `max_avg_borderline_high`: 6.0 / 7.0  

### LLM fallback (optional)

When `use_llm_fallback=True`, the Partner may call an LLM for **edge cases** only:

- Contradictory scores (e.g. gap ≥ 4 between max and min of the four dimensions, or one ≥ 8 and one ≤ 4).
- MEDIUM verdict with borderline average (6.0–7.0).
- MEDIUM with solid average but assumption_risks / missing assumptions affecting the decision.

The LLM path still returns a structured Partner output (e.g. MAYBE with human review); it does not re-score the startup.

### Output

Partner output includes: `decision` (YES/MAYBE/NO), `conviction_level` (1–10), `rationale`, `next_action`, `human_review_required`, `assumption_risks`.

---

## 4. How the Investment Memo Is Decided and Produced

The **Investment Memo** is not a “decision” in the sense of YES/NO. It is a **document** generated from a single **Startup** record (Scout + Review + Partner + Financials).

### Where it’s produced

- **Generator**: `backend/memo_generator.py` — class `MemoGenerator`, method `generate_memo(startup: Startup)`.
- **Format spec**: `resources/memos/investment_memo_v1.json` defines sections, order, tone (“analyst”), and that missing data should be marked (e.g. `[MISSING]`).

### What “decides” the memo content

1. **Which startup** is passed in (e.g. one that already has Scout, Review, and Partner data).
2. **The memo format** (sections and tone in `investment_memo_v1.json`).
3. **The code in MemoGenerator** that maps the Startup model into each section.

So the memo is “decided” by: **which startup record is selected** and **how that record is rendered** into the standard sections.

### Sections and data sources

| Section (order)        | Data source / logic |
|------------------------|----------------------|
| Header                 | Startup name, generated time, startup ID. |
| Company Overview       | Scout: name, one_line, sector, funding_stage, est_tam, scout_type, confidence. Missing → `[MISSING]`. |
| Problem & Opportunity | Scout: problem, solution, target_users, why_now. |
| Financials & Traction  | Financials block: traction_metrics, funding_history, valuation_est, ip_status. Missing → `[MISSING]`; consistency with review’s diligence_red_flags noted. |
| Reviewer Analysis     | Review: market/product/technical/execution (and optional defensibility) scores, average, **verdict**, overall_summary, key_risks, diligence_red_flags. |
| Partner Decision      | Partner: decision, conviction_level, rationale, next_action, human_review_required. MAYBE + human review → special label. |
| Next Steps            | Partner’s next_action (or “Pending decision” if no partner decision). |

### Metrics that drive the memo’s “decision” narrative

- **Reviewer**: verdict and the five dimension scores (and average of the four required ones), overall_summary, key_risks, diligence_red_flags, assumption_feedback (if surfaced elsewhere).
- **Partner**: decision (YES/MAYBE/NO), conviction_level, rationale, next_action, human_review_required, assumption_risks.

So the memo **reflects** the Reviewer’s verdict and scores and the Partner’s decision; it does not compute verdict or decision itself.

---

## 5. Summary Table

| Concept              | Decided by                    | Key metrics / inputs |
|----------------------|-------------------------------|-----------------------|
| **Reviewer verdict** | Reviewer LLM                  | Rubric thresholds; LLM outputs verdict + 5 dimension scores. |
| **Reviewer scores** | Reviewer LLM                  | Market, Product, Technical, Execution (1–10), optional Defensibility (1–10); rubric bands 1–4, 5–7, 8–10. |
| **Partner decision**| Partner rule engine           | Verdict, avg of 4 scores, key_risks, assumption_risks, critical/red-flag/contradiction checks; optional LLM for edge cases. |
| **Investment memo** | MemoGenerator (code)          | One Startup record; structure from investment_memo_v1; content from Scout, Review, Partner, Financials. |

---

## 6. Resource Files Reference

- **Reviewer rubric (dimensions + verdict thresholds + red flags)**: `resources/rubrics/evaluation_rubric_v1.json`
- **Reviewer rules (red-flag labels, verdict thresholds, hypothesis guidance)**: `resources/reviewer_rules.json`
- **Partner rules (verdict mapping, score thresholds, risks, LLM triggers)**: `resources/partner_rules.json`
- **Memo format (sections, tone)**: `resources/memos/investment_memo_v1.json`
- **Reviewer output schema**: `backend/reviewer/schema.py` (`ReviewerOutput`, `validate_reviewer_output`)
- **Reviewer prompt construction**: `backend/reviewer/base.py` (`_build_system_prompt`, `_call_llm_sync`)
- **Partner decision logic**: `backend/partner/decision.py` (`PartnerDecisionEngine.decide`)
- **Memo generation**: `backend/memo_generator.py` (`MemoGenerator.generate_memo`)
