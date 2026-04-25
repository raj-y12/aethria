"""
Investment Memo Generator.

Transforms nested Startup Pydantic models into professional Markdown Investment Memos.
Includes all Reviewer output fields (scores, verdict, overall_summary, key_risks, diligence_red_flags,
assumption_feedback, team_analysis, competition_analysis, business_model_analysis, investment_thesis,
risk_mitigation, score_reasoning). Surfaces Partner next_action, rationale, MAYBE + human_review_required.
"""
import json
import logging
from typing import Any, Dict, Optional
from datetime import datetime

from models import Startup
from utils.scoring import compute_overall_score, score_to_label

_logger_memo = logging.getLogger("memo_generation")

# Dimension labels for scores table (ReviewInfo field -> display name)
SCORE_DIMENSIONS = [
    ("market_score", "Market"),
    ("product_score", "Product"),
    ("technical_score", "Technical"),
    ("execution_score", "Execution"),
    ("defensibility_score", "Defensibility"),
]

# Score bands: 1–3 Weak, 4–5 Concerning, 6–7 Promising, 8–10 Strong (align with evaluation_rubric)
SCORE_BANDS = [(1, 3, "Weak"), (4, 5, "Concerning"), (6, 7, "Promising"), (8, 10, "Strong")]


def _get_score_band(score: int) -> str:
    for lo, hi, label in SCORE_BANDS:
        if lo <= score <= hi:
            return label
    return "—"


def _append_thesis_alignment_section(
    lines: list,
    startup: Startup,
    fund_thesis: Optional[Dict[str, Any]],
    for_display: bool,
) -> None:
    ri = startup.review_info
    has_ri_thesis = ri is not None and (
        getattr(ri, "thesis_alignment_score", None) is not None
        or getattr(ri, "thesis_fit_points", None)
        or getattr(ri, "thesis_deviation_points", None)
    )
    if not fund_thesis and not has_ri_thesis:
        return
    use_embedding_mode = False
    if fund_thesis:
        emb = fund_thesis.get("embedding") or []
        use_embedding_mode = isinstance(emb, list) and len(emb) > 0
    section_title = (
        "## Fund Thesis Alignment (AI-Enhanced)"
        if use_embedding_mode
        else "## Fund Thesis Alignment (Rule-Based)"
    )
    lines.append(section_title)
    lines.append("")
    if fund_thesis:
        pj = fund_thesis.get("parsed_json") or {}
        vid = fund_thesis.get("version_id", "—")
        vn = fund_thesis.get("version_number", "—")
        lines.append(f"**Active thesis:** `{vid}` (version {vn})")
        lines.append("")
        if not for_display:
            lines.append("**Structured mandate**")
            lines.append("")
            lines.append(f"```json\n{json.dumps(pj, indent=2)[:6000]}\n```")
            lines.append("")
        else:
            rules = pj.get("investment_rules") or []
            if isinstance(rules, list) and rules:
                lines.append("**Investment rules (excerpt)**")
                for r in rules[:5]:
                    lines.append(f"- {r}")
                lines.append("")
    if ri:
        tas = getattr(ri, "thesis_alignment_score", None)
        tm = getattr(ri, "thesis_matches_fund", None)
        tc = getattr(ri, "thesis_alignment_confidence", None)
        if tas is not None:
            if use_embedding_mode:
                lines.append(f"**Alignment score:** {float(tas):.2f} / 1.00")
            else:
                ten = float(tas) * 10.0
                lines.append(f"**Alignment score (rule-based):** {ten:.1f} / 10")
        if tm is not None:
            lines.append(f"**Matches fund mandate:** {'Yes' if tm else 'No'}")
        if tc is not None:
            conf_note = " (low — rule-based, no embeddings)" if not use_embedding_mode else ""
            lines.append(f"**Confidence (alignment assessment):** {float(tc):.2f} / 1.00{conf_note}")
        lines.append("")
        lines.append("**Why this fits the thesis**")
        lines.append("")
        fits = list(getattr(ri, "thesis_fit_points", None) or [])
        if fits:
            for b in fits:
                lines.append(f"- {b}")
        else:
            lines.append("- [MISSING]")
        lines.append("")
        lines.append("**Where it deviates**")
        lines.append("")
        devs = list(getattr(ri, "thesis_deviation_points", None) or [])
        if devs:
            for b in devs:
                lines.append(f"- {b}")
        else:
            lines.append("- [MISSING]")
        lines.append("")
    lines.append("---")
    lines.append("")


class MemoGenerator:
    """
    Generates professional VC Investment Memos from Startup records.
    
    Format: Professional Markdown with clear sections, red flags, next steps.
    Handles missing financial data gracefully; reflects missing data via diligence_red_flags where present.
    """

    def generate_memo(
        self,
        startup: Startup,
        for_display: bool = False,
        tenant_user_id: Optional[str] = None,
        fund_thesis: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Generate a complete investment memo for a startup.
        tenant_user_id: when set, logs structured tenant context for debugging async pipelines.
        """
        uid = (tenant_user_id or "").strip()
        if uid:
            _logger_memo.info(
                "event=memo_generation user_id=%s module=memo_generation startup_id=%s",
                uid[:24],
                startup.startup_id,
            )
        lines = []

        if not for_display:
            lines.append(f"# Investment Memo: {startup.scout_info.name}")
            lines.append("")
            lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            lines.append(f"**Startup ID:** {startup.startup_id}")
            lines.append("")
            lines.append("---")
            lines.append("")

        if not for_display:
            lines.append("## Company Overview")
            lines.append("")
            lines.append(f"**Name:** {startup.scout_info.name}")
            lines.append(f"**One-Line:** {startup.scout_info.one_line}")
            lines.append(f"**Sector:** {startup.scout_info.sector}")
            if startup.scout_info.funding_stage:
                lines.append(f"**Funding Stage:** {startup.scout_info.funding_stage}")
            else:
                lines.append("**Funding Stage:** [MISSING]")
            if startup.scout_info.est_tam:
                lines.append(f"**Est. TAM:** {startup.scout_info.est_tam}")
            else:
                lines.append("**Est. TAM:** [MISSING]")
            lines.append(f"**Scout Type:** {startup.scout_info.scout_type}")
            lines.append(f"**Confidence Score:** {startup.scout_info.confidence_score:.2f}")
            lines.append("")

        # Problem & Opportunity (Overview in old design) — separate paragraphs so heading is above text
        lines.append("## Overview")
        lines.append("")
        lines.append("**Problem**")
        lines.append("")
        lines.append(startup.scout_info.problem)
        lines.append("")
        lines.append("**Solution**")
        lines.append("")
        lines.append(startup.scout_info.solution)
        lines.append("")
        lines.append("**Target**")
        lines.append("")
        lines.append(startup.scout_info.target_users)
        lines.append("")
        lines.append("**Why now**")
        lines.append("")
        lines.append(startup.scout_info.why_now)
        lines.append("")

        _append_thesis_alignment_section(lines, startup, fund_thesis, for_display)

        # Financials & Traction
        lines.append("## Financials & Traction")
        lines.append("")
        missing_financials: list[str] = []
        if startup.financials.traction_metrics:
            lines.append(f"**Traction Metrics:** {startup.financials.traction_metrics}")
        else:
            lines.append("**Traction Metrics:** **[MISSING]**")
            missing_financials.append("Revenue/ARR data")
        if startup.financials.funding_history:
            lines.append(f"**Funding History:** {startup.financials.funding_history}")
        else:
            lines.append("**Funding History:** **[MISSING]**")
            missing_financials.append("Funding history")
        if startup.financials.valuation_est:
            lines.append(f"**Valuation Estimate:** {startup.financials.valuation_est}")
        else:
            lines.append("**Valuation Estimate:** **[MISSING]**")
            missing_financials.append("Valuation data")
        if startup.financials.ip_status:
            lines.append(f"**IP Status:** {startup.financials.ip_status}")
        else:
            lines.append("**IP Status:** [MISSING]")
        if missing_financials and startup.review_info and startup.review_info.diligence_red_flags:
            lines.append("")
            lines.append("*Missing financial data above is reflected in Diligence Red Flags.*")
        lines.append("")

        # Team & Founders; in display mode omit section when only [MISSING]
        team_analysis = (startup.review_info and (getattr(startup.review_info, "team_analysis", None) or [])) or []
        if (team_analysis and for_display) or not for_display:
            lines.append("## Team & Founders")
            lines.append("")
            if team_analysis:
                for item in team_analysis:
                    lines.append(f"- {item}")
            else:
                lines.append("- [MISSING]")
            lines.append("")

        # Competition & Market Position; in display mode omit when only [MISSING]
        comp_analysis = (startup.review_info and (getattr(startup.review_info, "competition_analysis", None) or [])) or []
        if (comp_analysis and for_display) or not for_display:
            lines.append("## Competition & Market Position")
            lines.append("")
            if comp_analysis:
                for item in comp_analysis:
                    lines.append(f"- {item}")
            else:
                lines.append("- [MISSING]")
            lines.append("")

        # Business Model & Monetization; in display mode omit when only [MISSING]
        bm_analysis = (startup.review_info and (getattr(startup.review_info, "business_model_analysis", None) or [])) or []
        if (bm_analysis and for_display) or not for_display:
            lines.append("## Business Model & Monetization")
            lines.append("")
            if bm_analysis:
                for item in bm_analysis:
                    lines.append(f"- {item}")
            else:
                lines.append("- [MISSING]")
            lines.append("")

        # Reviewer Analysis (scores table + summary + key risks; full version adds red flags / assumption feedback)
        if startup.review_info:
            ri = startup.review_info
            lines.append("## Reviewer Analysis")
            lines.append("")
            score_reasoning = getattr(ri, "score_reasoning", None) or {}
            lines.append("### Scores")
            lines.append("")
            lines.append("*1–3: Weak · 4–5: Concerning · 6–7: Promising · 8–10: Strong*")
            lines.append("")
            lines.append("| Dimension | Score | Band | Reasoning |")
            lines.append("|-----------|-------|------|-----------|")
            for dim_key, dim_label in SCORE_DIMENSIONS:
                score_val = getattr(ri, dim_key, None)
                score_str = f"{score_val}/10" if score_val is not None else "—"
                band = _get_score_band(score_val) if score_val is not None else "—"
                reasoning = (score_reasoning.get(dim_key) or "—").strip() if isinstance(score_reasoning, dict) else "—"
                if not reasoning:
                    reasoning = "—"
                reasoning_esc = reasoning.replace("|", "\\|")
                lines.append(f"| {dim_label} | {score_str} | {band} | {reasoning_esc} |")
            avg_score = compute_overall_score(ri.model_dump()) or 0.0
            avg_label = score_to_label(avg_score)
            lines.append("")
            lines.append(f"**Overall score (4 dimensions):** {avg_score:.1f} — {avg_label}")
            lines.append(
                f"Market ({ri.market_score:.1f}), Product ({ri.product_score:.1f}), "
                f"Technical ({ri.technical_score:.1f}), Execution ({ri.execution_score:.1f})"
            )
            def_val = ri.defensibility_score
            if def_val is not None:
                lines.append(f"Defensibility: {def_val:.1f} — {score_to_label(float(def_val))}")
            lines.append("")
            lines.append(f"**Quality assessment:** {ri.verdict}")
            lines.append("")
            lines.append("### Overall Summary")
            lines.append("")
            summary_text = getattr(ri, "overall_summary", "") or ""
            if summary_text.strip():
                lines.append(summary_text.strip())
            else:
                lines.append("[MISSING]")
            lines.append("")
            key_risks = getattr(ri, "key_risks", None) or []
            lines.append("### Key Risks")
            lines.append("")
            for risk in key_risks:
                lines.append(f"- {risk}")
            if not key_risks:
                lines.append("- [MISSING]")
            lines.append("")
            if not for_display:
                diligence_red_flags = getattr(ri, "diligence_red_flags", None) or []
                lines.append("### **Diligence Red Flags**")
                lines.append("")
                for flag in diligence_red_flags:
                    lines.append(f"- **{flag}**")
                if not diligence_red_flags:
                    lines.append("- [MISSING]")
                lines.append("")
                assumption_feedback = getattr(ri, "assumption_feedback", None) or []
                lines.append("### Assumption Feedback")
                lines.append("")
                for item in assumption_feedback:
                    lines.append(f"- {item}")
                if not assumption_feedback:
                    lines.append("- [MISSING]")
                lines.append("")
        else:
            lines.append("## Reviewer Analysis")
            lines.append("")
            lines.append("*Pending review*")
            lines.append("")

        # Investment Thesis; in display mode omit when only [MISSING]
        inv_thesis = (startup.review_info and (getattr(startup.review_info, "investment_thesis", None) or [])) or []
        if (inv_thesis and for_display) or not for_display:
            lines.append("## Investment Thesis")
            lines.append("")
            if inv_thesis:
                for item in inv_thesis:
                    lines.append(f"- {item}")
            else:
                lines.append("- [MISSING]")
            lines.append("")

        # Risk Mitigation; in display mode omit when only [MISSING]
        risk_mit = (startup.review_info and (getattr(startup.review_info, "risk_mitigation", None) or [])) or []
        if (risk_mit and for_display) or not for_display:
            lines.append("## Risk Mitigation")
            lines.append("")
            if risk_mit:
                for item in risk_mit:
                    lines.append(f"- {item}")
            else:
                lines.append("- [MISSING]")
            lines.append("")

        if not for_display:
            # Partner Decision
            if startup.partner_info:
                lines.append("## Decision")
                lines.append("")
                if startup.review_info:
                    lines.append(f"**Quality assessment:** {startup.review_info.verdict}")
                    lines.append("")
                decision_label = startup.partner_info.decision
                if startup.partner_info.decision == "MAYBE" and startup.partner_info.human_review_required:
                    decision_label = "MAYBE *(edge-case; human review required)*"
                lines.append(f"**Investment decision:** {decision_label}")
                lines.append(f"**Conviction Level:** {startup.partner_info.conviction_level}/10")
                lines.append("")
                lines.append("### Rationale")
                lines.append(startup.partner_info.rationale)
                lines.append("")
                if startup.partner_info.human_review_required:
                    lines.append("**⚠️ Human Review Required**")
                    lines.append("")
                lines.append("### Next Action")
                lines.append(f"**{startup.partner_info.next_action}**")
                lines.append("")
            else:
                lines.append("## Partner Decision")
                lines.append("")
                lines.append("*Pending decision*")
                lines.append("")

            # Deal Structure & Cap Table
            lines.append("## Deal Structure & Cap Table")
            lines.append("")
            if startup.financials.funding_history or startup.financials.valuation_est:
                if startup.financials.funding_history:
                    lines.append(f"- **Funding History:** {startup.financials.funding_history}")
                if startup.financials.valuation_est:
                    lines.append(f"- **Valuation Estimate:** {startup.financials.valuation_est}")
                lines.append("- **Round size / ownership:** [MISSING]")
            else:
                lines.append("- [MISSING]")
            lines.append("")

            # Exit Scenarios
            lines.append("## Exit Scenarios")
            lines.append("")
            lines.append("- Acquisition / IPO / multiples: [MISSING]")
            lines.append("")

            # Next Steps
            lines.append("## Next Steps")
            lines.append("")
            if startup.partner_info and startup.partner_info.next_action:
                lines.append(f"**{startup.partner_info.next_action}**")
            else:
                lines.append("*Awaiting partner decision*")
            lines.append("")
            lines.append("---")
            lines.append("")
            lines.append("*Memo generated by AETHRIA DealFlow OS*")
        return "\n".join(lines)

    def generate_summary(self, startup: Startup) -> str:
        """
        Generate a brief summary (one-pager format).
        Pulls average score and verdict from ReviewInfo.
        
        Args:
            startup: Startup Pydantic model
        
        Returns:
            Brief markdown summary
        """
        lines = []
        lines.append(f"# {startup.scout_info.name}")
        lines.append("")
        lines.append(f"**{startup.scout_info.one_line}**")
        lines.append("")
        lines.append(f"**Sector:** {startup.scout_info.sector}")
        if startup.review_info:
            avg_score = compute_overall_score(startup.review_info.model_dump()) or 0.0
            lines.append(
                f"**Review Score:** {avg_score:.1f} — {score_to_label(avg_score)} ({startup.review_info.verdict})"
            )
        if startup.partner_info:
            lines.append(f"**Decision:** {startup.partner_info.decision} (Conviction: {startup.partner_info.conviction_level}/10)")
            if startup.partner_info.human_review_required:
                lines.append("**⚠️ Human review required**")
        lines.append("")
        lines.append(f"**Next Action:** {startup.partner_info.next_action if startup.partner_info else 'Pending'}")
        return "\n".join(lines)
