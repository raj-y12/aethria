"""
Investment Memo Generator.

Transforms nested Startup Pydantic models into professional Markdown Investment Memos.
Includes qualitative Reviewer output (overall_summary, key_risks, diligence_red_flags,
assumption_feedback, team_analysis, competition_analysis, business_model_analysis, investment_thesis,
risk_mitigation). Canonical evaluation owns every displayed assessment score.
"""
import json
import logging
import os
import resource
import time
from typing import Any, Dict, Optional
from datetime import datetime
from utils.timeutil import utcnow

from models import Startup
from research.recency import memo_recency_note
from utils.traction_extraction import render_traction_facts

_logger_memo = logging.getLogger("memo_generation")


def _rss_mb() -> float:
    try:
        page_size = os.sysconf("SC_PAGE_SIZE")
        with open("/proc/self/statm", "r", encoding="utf-8") as f:
            parts = f.read().split()
        if len(parts) >= 2:
            return round((int(parts[1]) * page_size) / (1024 * 1024), 1)
    except Exception:
        pass
    try:
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return round((rss / (1024 * 1024)) if rss > 10_000_000 else (rss / 1024), 1)
    except Exception:
        return -1.0

def _append_investment_read_section(lines: list, startup: Startup, for_display: bool) -> None:
    """Render the investment read (reviewer_rules v2+) as the memo's lead.

    Narrative only — nothing here feeds a score. In display mode the section is
    omitted when nothing met the evidence bar; the full memo prints the named
    absence instead, so a reader can tell "no read" from "read not attempted".
    """
    def _sentence(text: str) -> str:
        text = str(text or "").strip()
        return text if not text or text[-1] in ".!?" else text + "."

    ri = startup.review_info
    reframe = (ri and getattr(ri, "reframe", None)) or {}
    slope = (ri and getattr(ri, "capability_slope", None)) or {}
    fluency = (ri and getattr(ri, "founder_fluency", None)) or []
    if not (reframe or slope or fluency):
        if for_display:
            return
        lines.append("## The Read")
        lines.append("")
        lines.append(
            "No read recorded. The evidence does not establish a demonstrated capability, "
            "a resolved founder history, or a question the obvious framing gets wrong. "
            "This is a named absence, not an omission."
        )
        lines.append("")
        return

    lines.append("## The Read")
    lines.append("")
    if reframe:
        lines.append(f"**The obvious question.** {reframe.get('obvious_question', '')}")
        lines.append("")
        lines.append(f"**Why it misleads.** {reframe.get('why_it_misleads', '')}")
        lines.append("")
        lines.append(f"**The question that decides it.** {reframe.get('real_question', '')}")
        lines.append("")
    if slope:
        lines.append(
            "**Capability slope.** Hardest instance handled today: "
            + _sentence(slope.get("hardest_instance", ""))
        )
        lines.append("")
        # Grouped under one lead-in each; repeating the label per bullet reads as
        # a stutter once there is more than one adjacency.
        for label, key in (("Downhill from there", "downhill"), ("Still blocked by", "blocked_by")):
            items = slope.get(key) or []
            if not items:
                continue
            lines.append(f"*{label}*")
            lines.append("")
            for item in items:
                lines.append(f"- {_sentence(item)}")
            lines.append("")
        evidence = str(slope.get("evidence") or "").strip()
        if evidence:
            lines.append(f"*Evidence: {evidence}*")
            lines.append("")
    if fluency:
        lines.append("**Founder fluency**")
        lines.append("")
        for entry in fluency:
            if not isinstance(entry, dict):
                continue
            head = f"- **{entry.get('founder', '')}** — {_sentence(entry.get('prior_domain', ''))}"
            fluent_in = "; ".join(entry.get("fluent_in") or [])
            unlocks = "; ".join(entry.get("unlocks") or [])
            if fluent_in:
                head += f" Fluent in {_sentence(fluent_in)}"
            if unlocks:
                # "without retraining" is the definition of the field, not a
                # per-founder qualifier; restating it strands the phrase after a
                # semicolon-separated list.
                head += f" Unlocks {_sentence(unlocks)}"
            lines.append(head)
            evidence = str(entry.get("evidence") or "").strip()
            if evidence:
                lines.append(f"  - *Evidence: {evidence}*")
        lines.append("")


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
        lines.append(f"**Active thesis:** version {vn}" if for_display else f"**Active thesis:** `{vid}` (version {vn})")
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
            lines.append("- Not provided")
        lines.append("")
        lines.append("**Where it deviates**")
        lines.append("")
        devs = list(getattr(ri, "thesis_deviation_points", None) or [])
        if devs:
            for b in devs:
                lines.append(f"- {b}")
        else:
            lines.append("- Not provided")
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
        started_at = time.perf_counter()
        rss_before = _rss_mb()
        if uid:
            _logger_memo.info(
                "event=memo_generation_start user_id=%s module=memo_generation startup_id=%s rss_mb_before=%.1f",
                uid[:24],
                startup.startup_id,
                rss_before,
            )
        lines = []

        if not for_display:
            lines.append(f"# Investment Memo: {startup.scout_info.name}")
            lines.append("")
            lines.append(f"**Generated:** {utcnow().strftime('%Y-%m-%d %H:%M:%S')}")
            lines.append(memo_recency_note())
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
                lines.append("**Funding Stage:** Not provided")
            if startup.scout_info.est_tam:
                lines.append(f"**Est. TAM:** {startup.scout_info.est_tam}")
            else:
                lines.append("**Est. TAM:** Not provided")
            # Firmographics lifted verbatim out of retrieved evidence. Printed
            # because the reviewer once flagged "Missing revenue or traction
            # data" while this text sat unread in the same record — surfacing it
            # to the reader is what makes that failure visible next time.
            traction = render_traction_facts(getattr(startup.scout_info, "traction_facts", None))
            if traction:
                lines.append(f"**Traction (from evidence):** {traction}")
            lines.append(f"**Scout Type:** {startup.scout_info.scout_type}")
            lines.append(f"**Confidence Score:** {startup.scout_info.confidence_score:.2f}")
            lines.append("")

        # The read leads: what the scores cannot say, before the facts they rank.
        _append_investment_read_section(lines, startup, for_display)

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
            lines.append("**Traction Metrics:** **Not provided**")
            missing_financials.append("Revenue/ARR data")
        if startup.financials.funding_history:
            lines.append(f"**Funding History:** {startup.financials.funding_history}")
        else:
            lines.append("**Funding History:** **Not provided**")
            missing_financials.append("Funding history")
        if startup.financials.valuation_est:
            lines.append(f"**Valuation Estimate:** {startup.financials.valuation_est}")
        else:
            lines.append("**Valuation Estimate:** **Not provided**")
            missing_financials.append("Valuation data")
        if startup.financials.ip_status:
            lines.append(f"**IP Status:** {startup.financials.ip_status}")
        else:
            lines.append("**IP Status:** Not provided")
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
                lines.append("- Not provided")
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
                lines.append("- Not provided")
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
                lines.append("- Not provided")
            lines.append("")

        # Reviewer research is qualitative. Canonical evaluation renders the
        # assessment ledger elsewhere; never reconstruct it from reviewer fields.
        if startup.review_info:
            ri = startup.review_info
            lines.append("## Reviewer Research")
            lines.append("")
            lines.append("### Overall Summary")
            lines.append("")
            summary_text = getattr(ri, "overall_summary", "") or ""
            if summary_text.strip():
                lines.append(summary_text.strip())
            else:
                lines.append("Not provided")
            lines.append("")
            key_risks = getattr(ri, "key_risks", None) or []
            lines.append("### Key Risks")
            lines.append("")
            for risk in key_risks:
                lines.append(f"- {risk}")
            if not key_risks:
                lines.append("- Not provided")
            lines.append("")
            contradiction_guards = [
                getattr(ri, "contradiction_guard", None),
                getattr(startup.partner_info, "contradiction_guard", None) if startup.partner_info else None,
            ]
            corrections = [
                correction
                for guard in contradiction_guards
                if isinstance(guard, dict)
                for correction in (guard.get("corrections", []) or [])
            ]
            if corrections:
                lines.append("### Evidence Guard")
                lines.append("")
                lines.append("Material Reviewer judgments were checked against canonical decision-time evidence:")
                for correction in corrections:
                    state = str(correction.get("state") or "uncertain").replace("_", " ")
                    criterion = str(correction.get("criterion") or "unknown")
                    sources = sorted({str(item.get("source_locator")) for item in correction.get("evidence", []) if item.get("source_locator")})
                    source_text = f" Sources: {', '.join(sources)}." if sources else ""
                    lines.append(f"- **{criterion} — {state}.** {correction.get('guarded') or 'Reassess against the evidence.'}{source_text}")
                lines.append("")
            if not for_display:
                diligence_red_flags = getattr(ri, "diligence_red_flags", None) or []
                lines.append("### **Diligence Red Flags**")
                lines.append("")
                for flag in diligence_red_flags:
                    lines.append(f"- **{flag}**")
                if not diligence_red_flags:
                    lines.append("- Not provided")
                lines.append("")
                assumption_feedback = getattr(ri, "assumption_feedback", None) or []
                lines.append("### Assumption Feedback")
                lines.append("")
                for item in assumption_feedback:
                    lines.append(f"- {item}")
                if not assumption_feedback:
                    lines.append("- Not provided")
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
                lines.append("- Not provided")
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
                lines.append("- Not provided")
            lines.append("")

        if not for_display:
            # Partner Decision
            if startup.partner_info:
                lines.append("## Decision")
                lines.append("")
                decision_label = startup.partner_info.recommendation
                if startup.partner_info.human_review_required:
                    decision_label += " *(human review required)*"
                lines.append(f"**Investment decision:** {decision_label}")
                lines.append(f"**Confidence:** {startup.partner_info.confidence:.0%}")
                lines.append("")
                lines.append("### Rationale")
                lines.append(startup.partner_info.decision_rationale)
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
                lines.append("- **Round size / ownership:** Not provided")
            else:
                lines.append("- Not provided")
            lines.append("")

            # Exit Scenarios
            lines.append("## Exit Scenarios")
            lines.append("")
            lines.append("- Acquisition / IPO / multiples: Not provided")
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
        memo = "\n".join(lines)
        if uid:
            _logger_memo.info(
                "event=memo_generation_done user_id=%s module=memo_generation startup_id=%s rss_mb_after=%.1f duration_s=%.2f memo_chars=%s",
                uid[:24],
                startup.startup_id,
                _rss_mb(),
                time.perf_counter() - started_at,
                len(memo),
            )
        return memo

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
            lines.append("**Research:** Complete — canonical evidence assessment pending or available in the deal memo.")
        if startup.partner_info:
            lines.append(
                f"**Decision:** {startup.partner_info.recommendation} "
                f"(Confidence: {startup.partner_info.confidence:.0%})"
            )
            if startup.partner_info.human_review_required:
                lines.append("**⚠️ Human review required**")
        lines.append("")
        lines.append(f"**Next Action:** {startup.partner_info.next_action if startup.partner_info else 'Pending'}")
        return "\n".join(lines)
