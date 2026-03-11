"""
Partner decision engine.
Rule-based, deterministic decision making.
Uses /resources/partner_rules.json for thresholds, red flags, and LLM fallback triggers.
Default mode: NO LLM calls. LLM only for edge cases (contradictory scores, MEDIUM borderline, missing assumptions).
"""
import os
import json
import asyncio
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from concurrent.futures import ThreadPoolExecutor

from openai import OpenAI
from partner.schema import PartnerOutput, validate_partner_output


logger = logging.getLogger(__name__)


def _load_partner_rules() -> Dict[str, Any]:
    """
    Load partner rules from /resources/partner_rules.json.
    Returns empty dict if file missing or invalid; callers use defaults.
    """
    try:
        project_root = Path(__file__).resolve().parent.parent.parent
        rules_path = project_root / "resources" / "partner_rules.json"
        if not rules_path.exists():
            logger.warning("partner_rules.json not found; using in-code defaults.")
            return {}
        with open(rules_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Could not load partner rules: {e}. Using defaults.")
        return {}


class PartnerDecisionEngine:
    """
    Rule-based decision engine for Partner layer.
    Applies deterministic rules from /resources/partner_rules.json to Reviewer outputs.
    Hypothesis-aware: uses assumption_feedback and Scout hypothesis fields to flag
    assumption_risks and adjust conviction. Conservative, opinionated, cost-aware.
    """

    def __init__(
        self,
        use_llm_fallback: bool = True,
        api_key: str = None,
        model: str = None,
        portfolio_store=None,
    ):
        """
        Initialize the decision engine.
        Loads rules from /resources/partner_rules.json.
        Args:
            use_llm_fallback: Whether to use LLM for edge cases (default: True)
            api_key: OpenAI API key for real LLM calls (falls back to env)
            model: Model name (falls back to env PARTNER_MODEL or gpt-5-nano)
            portfolio_store: Optional PortfolioStore for portfolio awareness
        """
        self.use_llm_fallback = use_llm_fallback
        self.logger = logging.getLogger("partner.decision")
        self.llm_call_count = 0
        self._rules: Dict[str, Any] = _load_partner_rules()
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self.model = model or os.getenv("PARTNER_MODEL", "gpt-5-nano")
        if self.api_key:
            self.client = OpenAI(api_key=self.api_key)
            self.executor = ThreadPoolExecutor(max_workers=1)
        else:
            self.client = None
        self._last_token_usage: Optional[Dict[str, int]] = None
        self.portfolio_store = portfolio_store

    def _verdict_label(self, verdict: str) -> str:
        """Human-readable quality label for verdict. Uses quality_labels from rules."""
        labels = self._rules.get("quality_labels", {})
        return labels.get(verdict, verdict)

    def _get_rules(self) -> Dict[str, Any]:
        """Return loaded partner rules (cached after init)."""
        return self._rules

    def _get_portfolio_context(self) -> dict:
        """Load portfolio from store and compute context summary."""
        if not self.portfolio_store:
            return {}
        try:
            portfolio_companies = self.portfolio_store.get_all_portfolio()
            startups = self.portfolio_store.get_all_startups()
            sector_counts: Dict[str, int] = {}
            stage_counts: Dict[str, int] = {}
            for s in startups:
                sector = s.get("sector", "Unknown")
                sector_counts[sector] = sector_counts.get(sector, 0) + 1
            for p in portfolio_companies:
                sid = p.get("startup_id", "")
                s = self.portfolio_store.get_startup(sid)
                if s:
                    stage = s.get("metadata", {}).get("funding_stage") or "Unknown"
                    stage_counts[stage] = stage_counts.get(stage, 0) + 1
            return {
                "sector_counts": sector_counts,
                "stage_counts": stage_counts,
                "total_portfolio_size": len(portfolio_companies),
            }
        except Exception as e:
            self.logger.warning(f"Could not load portfolio context: {e}")
            return {}

    def decide(self, scout_output: Dict[str, Any], review_output: Dict[str, Any], context_memo: str = "") -> Dict[str, Any]:
        """
        Make an investment decision based on Scout and Reviewer outputs.
        Uses assumption_feedback and Scout hypothesis (primary_thesis, key_assumptions,
        biggest_unknown) to compute assumption_risks and adjust conviction.
        Args:
            scout_output: Valid ScoutOutput dict (may include primary_thesis, key_assumptions, biggest_unknown, sector, funding_stage)
            review_output: Valid ReviewerOutput dict (may include assumption_feedback; defaults to [])
            context_memo: Optional pre-decision memo text for LLM context
        Returns:
            PartnerOutput with decision, conviction_level, rationale, next_action,
            human_review_required, assumption_risks. Legacy INVEST/WATCH/PASS mapped to YES/MAYBE/NO.
        """
        rules = self._get_rules()
        verdict_rules = rules.get("verdict_rules", {})
        score_thresholds = rules.get("score_thresholds", {})
        next_actions = rules.get("next_actions", {})

        portfolio_context = self._get_portfolio_context() if self.portfolio_store else {}

        market_score = review_output.get("market_score", 0)
        product_score = review_output.get("product_score", 0)
        technical_score = review_output.get("technical_score", 0)
        execution_score = review_output.get("execution_score", 0)
        verdict = review_output.get("verdict", "WEAK")
        key_risks = review_output.get("key_risks", [])
        assumption_feedback: List[str] = review_output.get("assumption_feedback") or []

        avg_score = (market_score + product_score + technical_score + execution_score) / 4.0
        min_avg_pass = score_thresholds.get("min_avg_pass", 6.0)
        min_avg_strong_yes = score_thresholds.get("min_avg_strong_yes", 8.0)
        min_avg_medium_maybe = score_thresholds.get("min_avg_medium_maybe", 7.0)
        min_avg_borderline_low = score_thresholds.get("min_avg_borderline_low", 6.0)
        max_avg_borderline_high = score_thresholds.get("max_avg_borderline_high", 7.0)

        assumption_risks = self._compute_assumption_risks(
            scout_output, review_output, assumption_feedback
        )
        conviction_adjust = -1 if assumption_risks else 0

        scout_confidence = scout_output.get("confidence", 0.5)
        if scout_confidence < 0.5:
            conviction_adjust -= 1

        # Qualitative VC inputs: team and business model presence/quality
        has_missing_team = self._has_missing_team(review_output, rules)
        has_missing_business_model = self._has_missing_business_model(review_output, rules)
        if has_missing_team:
            conviction_adjust -= 1
        if has_missing_business_model:
            conviction_adjust -= 1
        # Strong team/business model (present and not [MISSING]-only) can boost conviction
        if not has_missing_team and self._has_strong_qualitative(review_output.get("team_analysis") or []):
            conviction_adjust += 1
        if not has_missing_business_model and self._has_strong_qualitative(review_output.get("business_model_analysis") or []):
            conviction_adjust += 1

        has_critical_risk = self._has_critical_risk(key_risks, rules)
        has_red_flags = self._has_red_flags(key_risks, rules)
        has_contradiction = self._has_contradictory_scores(
            market_score, product_score, technical_score, execution_score, rules
        )
        has_missing_assumptions = self._has_missing_assumptions_affecting_decision(
            assumption_feedback, assumption_risks, rules
        )
        has_missing_critical_qualitative = has_missing_team or has_missing_business_model

        # Rule 1: WEAK verdict → NO
        weak_rule = verdict_rules.get("WEAK", {})
        if verdict == "WEAK":
            label = self._verdict_label(verdict)
            result = self._create_decision(
                decision=weak_rule.get("decision", "NO"),
                confidence=weak_rule.get("conviction_level", 9),
                rationale=(
                    f"Quality assessment: {label}. Average score: {avg_score:.1f}/10. "
                    f"Not suitable for investment consideration."
                ),
                next_action=weak_rule.get("next_action", "Pass - Market too crowded / Low quality"),
                human_review_required=weak_rule.get("human_review_required", False),
                assumption_risks=assumption_risks,
            )
            result["portfolio_context_at_decision"] = portfolio_context or None
            result["memo_at_decision"] = context_memo or None
            return result

        # Portfolio awareness rules (after WEAK → NO)
        startup_sector = scout_output.get("sector", "")
        startup_funding_stage = scout_output.get("funding_stage")
        if portfolio_context:
            sector_counts = portfolio_context.get("sector_counts", {})
            total = portfolio_context.get("total_portfolio_size", 0)
            if sector_counts.get(startup_sector, 0) >= 3:
                conviction_adjust -= 2
            if total > 20 and startup_funding_stage == "Pre-Seed":
                conviction_adjust -= 1

        # Rule 2: Critical risks → NO
        if has_critical_risk:
            result = self._create_decision(
                decision="NO",
                confidence=8 + conviction_adjust,
                rationale=(
                    f"Critical risks identified (regulatory or execution impossibility). "
                    f"Average score: {avg_score:.1f}/10. Risk too high for investment."
                ),
                next_action=next_actions.get("critical_risks", "Pass - Critical risks too high"),
                human_review_required=False,
                assumption_risks=assumption_risks,
            )
            result["portfolio_context_at_decision"] = portfolio_context or None
            result["memo_at_decision"] = context_memo or None
            return result

        # Rule 3: Low average score → NO
        if avg_score < min_avg_pass:
            label = self._verdict_label(verdict)
            result = self._create_decision(
                decision="NO",
                confidence=7 + conviction_adjust,
                rationale=(
                    f"Average score {avg_score:.1f}/10 below threshold ({min_avg_pass}). "
                    f"Quality: {label}. Insufficient quality for investment."
                ),
                next_action=next_actions.get("low_scores", "Pass - Low scores"),
                human_review_required=False,
                assumption_risks=assumption_risks,
            )
            result["portfolio_context_at_decision"] = portfolio_context or None
            result["memo_at_decision"] = context_memo or None
            return result

        # Rule 4: STRONG verdict + high score → YES
        strong_rule = verdict_rules.get("STRONG", {})
        if verdict == "STRONG" and avg_score >= min_avg_strong_yes:
            next_action = (
                next_actions.get("request_cap_table_and_review", "Request Cap Table + Technical Code Review")
                if has_red_flags
                else next_actions.get("request_cap_table", "Request Cap Table")
            )
            human_review = strong_rule.get("human_review_required_yes", True) or has_missing_critical_qualitative
            label = self._verdict_label(verdict)
            rationale_parts = (
                f"Quality: {label}. High average score ({avg_score:.1f}/10). "
                f"Market: {market_score}/10, Product: {product_score}/10, "
                f"Technical: {technical_score}/10, Execution: {execution_score}/10. "
                f"Meets investment criteria."
            )
            if has_missing_critical_qualitative:
                rationale_parts += " Team or business model detail missing; human review recommended."
            if portfolio_context and portfolio_context.get("sector_counts", {}).get(startup_sector, 0) >= 3:
                rationale_parts += " sector_concentration_risk"
            result = self._create_decision(
                decision=strong_rule.get("decision_yes", "YES"),
                confidence=strong_rule.get("conviction_level_yes", 8) + conviction_adjust,
                rationale=rationale_parts,
                next_action=next_action,
                human_review_required=human_review,
                assumption_risks=assumption_risks,
            )
            result["portfolio_context_at_decision"] = portfolio_context or None
            result["memo_at_decision"] = context_memo or None
            return result

        # Check reviewer disagreement for LLM trigger
        reviewer_disagreement = review_output.get("reviewer_disagreement", False)

        # Rule 5: MEDIUM verdict + good score → MAYBE (or LLM if contradictory / missing assumptions / missing qualitative / disagreement)
        medium_rule = verdict_rules.get("MEDIUM", {})
        if verdict == "MEDIUM" and avg_score >= min_avg_medium_maybe:
            llm_triggers = rules.get("llm_fallback_triggers", {})
            trigger_reason = ""
            if has_contradiction and llm_triggers.get("contradictory_scores", True):
                trigger_reason = "Contradictory scores detected (gap >= threshold)"
            elif has_missing_assumptions and llm_triggers.get("missing_assumptions_affecting_decision", True):
                trigger_reason = "Missing assumptions affecting decision"
            elif has_missing_critical_qualitative and llm_triggers.get("missing_critical_qualitative", True):
                trigger_reason = "Missing critical qualitative data (team/business model)"
            elif reviewer_disagreement and llm_triggers.get("reviewer_disagreement", False):
                trigger_reason = "Reviewer disagreement detected"
            use_llm = self.use_llm_fallback and bool(trigger_reason)
            if use_llm:
                result = self._decide_with_llm(
                    scout_output, review_output, assumption_risks,
                    trigger_reason=trigger_reason, context_memo=context_memo,
                    portfolio_context=portfolio_context,
                )
                result["portfolio_context_at_decision"] = portfolio_context or None
                result["memo_at_decision"] = context_memo or None
                return result
            label = self._verdict_label(verdict)
            rationale_text = (
                f"Quality: {label}. Solid average score ({avg_score:.1f}/10). "
                f"Market: {market_score}/10, Product: {product_score}/10, "
                f"Technical: {technical_score}/10, Execution: {execution_score}/10. "
                f"Worth monitoring for market signals or team development."
            )
            if portfolio_context and portfolio_context.get("sector_counts", {}).get(startup_sector, 0) >= 3:
                rationale_text += " sector_concentration_risk"
            result = self._create_decision(
                decision=medium_rule.get("decision_maybe", "MAYBE"),
                confidence=medium_rule.get("conviction_level_maybe", 6) + conviction_adjust,
                rationale=rationale_text,
                next_action=next_actions.get("monitor", "Monitor market and track progress"),
                human_review_required=False,
                assumption_risks=assumption_risks,
            )
            result["portfolio_context_at_decision"] = portfolio_context or None
            result["memo_at_decision"] = context_memo or None
            return result

        # Rule 6: MEDIUM verdict, borderline score → LLM or PASS
        if verdict == "MEDIUM" and min_avg_borderline_low <= avg_score < max_avg_borderline_high:
            llm_triggers = rules.get("llm_fallback_triggers", {})
            use_llm = self.use_llm_fallback and llm_triggers.get("medium_borderline_avg", True)
            if use_llm:
                trigger_reason = "MEDIUM verdict with borderline average score"
                result = self._decide_with_llm(
                    scout_output, review_output, assumption_risks,
                    trigger_reason=trigger_reason, context_memo=context_memo,
                    portfolio_context=portfolio_context,
                )
                result["portfolio_context_at_decision"] = portfolio_context or None
                result["memo_at_decision"] = context_memo or None
                return result
            label = self._verdict_label(verdict)
            result = self._create_decision(
                decision=medium_rule.get("decision_borderline_no_llm", "NO"),
                confidence=medium_rule.get("conviction_level_borderline", 5) + conviction_adjust,
                rationale=(
                    f"Quality: {label}, but average score ({avg_score:.1f}/10) below threshold. "
                    f"Borderline case, defaulting to PASS."
                ),
                next_action=medium_rule.get("next_action_borderline", "Reject - borderline quality"),
                human_review_required=False,
                assumption_risks=assumption_risks,
            )
            result["portfolio_context_at_decision"] = portfolio_context or None
            result["memo_at_decision"] = context_memo or None
            return result

        # Default: NO
        label = self._verdict_label(verdict)
        result = self._create_decision(
            decision="NO",
            confidence=6 + conviction_adjust,
            rationale=(
                f"Does not meet investment criteria. Quality: {label}. "
                f"Average score: {avg_score:.1f}/10."
            ),
            next_action=next_actions.get("default_no", "Pass - Does not meet criteria"),
            human_review_required=False,
            assumption_risks=assumption_risks,
        )
        result["portfolio_context_at_decision"] = portfolio_context or None
        result["memo_at_decision"] = context_memo or None
        return result

    def _compute_assumption_risks(
        self,
        scout_output: Dict[str, Any],
        review_output: Dict[str, Any],
        assumption_feedback: List[str],
    ) -> List[str]:
        """
        Build list of critical unknowns or assumption concerns from Reviewer assumption_feedback
        and Scout hypothesis (primary_thesis, key_assumptions, biggest_unknown).
        Flags items that may affect decision; default empty if none identified.
        """
        risks: List[str] = []
        rules = self._get_rules()
        keywords = rules.get("assumption_risk_keywords", [
            "critical unknown", "unvalidated assumption", "weak assumption",
            "could invalidate", "unresolved", "missing validation",
        ])
        feedback_lower = [f.lower() for f in assumption_feedback]
        for i, fb in enumerate(assumption_feedback):
            if any(kw in feedback_lower[i] for kw in keywords):
                risks.append(fb)
        if not risks and assumption_feedback:
            for fb in assumption_feedback:
                if any(w in fb.lower() for w in ("unknown", "unclear", "unvalidated", "risk")):
                    risks.append(fb)
        biggest_unknown = scout_output.get("biggest_unknown") or ""
        if biggest_unknown.strip() and not any(biggest_unknown.strip() in r for r in risks):
            risks.append(f"Biggest unknown: {biggest_unknown.strip()}")
        return risks[:10]

    def _has_critical_risk(self, key_risks: List[str], rules: Dict[str, Any]) -> bool:
        """Check if any risk indicates regulatory or execution impossibility (from rules)."""
        keywords = rules.get("critical_risk_keywords", [
            "regulatory", "regulation", "legal impossibility", "execution impossibility",
            "cannot be executed", "regulatory ban", "prohibited by law",
        ])
        risks_lower = [r.lower() for r in key_risks]
        for risk in risks_lower:
            for keyword in keywords:
                if keyword in risk:
                    return True
        return False

    def _has_red_flags(self, key_risks: List[str], rules: Dict[str, Any]) -> bool:
        """Check for missing-data or red-flag phrasing (from rules)."""
        keywords = rules.get("red_flag_keywords", ["missing", "red flag"])
        return any(
            any(kw in risk.lower() for kw in keywords)
            for risk in key_risks
        )

    def _has_contradictory_scores(
        self,
        market: int,
        product: int,
        technical: int,
        execution: int,
        rules: Dict[str, Any],
    ) -> bool:
        """Detect contradictory scores using thresholds from rules."""
        cfg = rules.get("contradictory_scores", {})
        min_gap = cfg.get("min_gap", 4)
        high_threshold = cfg.get("high_threshold", 8)
        low_threshold = cfg.get("low_threshold", 4)
        scores = [market, product, technical, execution]
        max_s, min_s = max(scores), min(scores)
        if max_s - min_s >= min_gap:
            return True
        if max_s >= high_threshold and min_s <= low_threshold:
            return True
        return False

    def _has_missing_assumptions_affecting_decision(
        self,
        assumption_feedback: List[str],
        assumption_risks: List[str],
        rules: Dict[str, Any],
    ) -> bool:
        """True if Reviewer flagged critical unknowns that could affect the decision."""
        return len(assumption_risks) > 0

    def _has_missing_team(self, review_output: Dict[str, Any], rules: Dict[str, Any]) -> bool:
        """True if team_analysis is absent or only [MISSING] placeholders."""
        team = review_output.get("team_analysis") or []
        if not team:
            return True
        missing_keywords = rules.get("missing_qualitative_keywords", ["[MISSING]", "missing", "absent", "n/a"])
        combined = " ".join(t.lower() for t in team)
        return any(kw in combined for kw in missing_keywords) and len(team) <= 2

    def _has_missing_business_model(self, review_output: Dict[str, Any], rules: Dict[str, Any]) -> bool:
        """True if business_model_analysis is absent or only [MISSING] placeholders."""
        bm = review_output.get("business_model_analysis") or []
        if not bm:
            return True
        missing_keywords = rules.get("missing_qualitative_keywords", ["[MISSING]", "missing", "absent", "n/a"])
        combined = " ".join(t.lower() for t in bm)
        return any(kw in combined for kw in missing_keywords) and len(bm) <= 2

    def _has_strong_qualitative(self, items: List[str]) -> bool:
        """True if list has substantive content (not just [MISSING] or short placeholders)."""
        if not items or len(items) < 2:
            return False
        missing = "[missing]"
        substantive = [s for s in items if missing not in s.lower() and len(s.strip()) > 20]
        return len(substantive) >= 1

    def _create_decision(
        self,
        decision: str,
        confidence: int,
        rationale: str,
        next_action: str,
        human_review_required: bool,
        assumption_risks: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Build a decision dict conforming to PartnerOutput.
        Maps legacy INVEST/WATCH/PASS to YES/MAYBE/NO. Clamps conviction to 1-10.
        """
        decision_map = {"INVEST": "YES", "WATCH": "MAYBE", "PASS": "NO"}
        mapped = decision_map.get(decision, decision)
        conviction = max(1, min(10, confidence))
        return {
            "decision": mapped,
            "conviction_level": conviction,
            "rationale": rationale,
            "next_action": next_action,
            "human_review_required": human_review_required,
            "assumption_risks": assumption_risks if assumption_risks is not None else [],
        }

    def _decide_with_llm(
        self,
        scout_output: Dict[str, Any],
        review_output: Dict[str, Any],
        assumption_risks: List[str],
        trigger_reason: str = "",
        context_memo: str = "",
        portfolio_context: dict = None,
    ) -> Dict[str, Any]:
        """
        Use LLM for nuanced decision in edge cases.
        If self.client is None, falls back to hardcoded behavior.
        Otherwise makes a real OpenAI call with structured JSON output.
        """
        self.llm_call_count += 1
        self.logger.warning(
            f"LLM call #{self.llm_call_count} triggered for edge case decision. "
            f"Company: {scout_output.get('name', 'Unknown')}"
        )

        avg_score = (
            review_output.get("market_score", 0)
            + review_output.get("product_score", 0)
            + review_output.get("technical_score", 0)
            + review_output.get("execution_score", 0)
        ) / 4.0
        verdict = review_output.get("verdict", "MEDIUM")
        rules = self._get_rules()
        next_actions = rules.get("next_actions", {})

        if self.client is None:
            if verdict == "MEDIUM" and 6.0 <= avg_score < 7.0:
                label = self._verdict_label(verdict)
                result = self._create_decision(
                    decision="MAYBE",
                    confidence=5,
                    rationale=(
                        f"Edge case: Quality {label} with borderline score ({avg_score:.1f}/10). "
                        f"LLM-assisted analysis suggests monitoring rather than immediate rejection. "
                        f"Requires human judgment."
                    ),
                    next_action=next_actions.get("human_review_monitor", "Human review required - monitor closely"),
                    human_review_required=True,
                    assumption_risks=assumption_risks,
                )
            else:
                label = self._verdict_label(verdict)
                result = self._create_decision(
                    decision="MAYBE",
                    confidence=4,
                    rationale=(
                        f"Contradictory scores or critical assumptions detected. "
                        f"LLM-assisted analysis suggests cautious monitoring. "
                        f"Average score: {avg_score:.1f}/10, Quality: {label}. Requires deeper analysis."
                    ),
                    next_action=next_actions.get("human_review_contradictions", "Human review required - analyze contradictions"),
                    human_review_required=True,
                    assumption_risks=assumption_risks,
                )
            result["llm_fallback_reason"] = trigger_reason
            return result

        score_reasoning = review_output.get("score_reasoning") or {}
        diligence_red_flags = review_output.get("diligence_red_flags", [])
        team_analysis = review_output.get("team_analysis") or []
        competition_analysis = review_output.get("competition_analysis") or []
        business_model_analysis = review_output.get("business_model_analysis") or []

        if context_memo:
            context_block = f"CONTEXT:\n{context_memo}"
        else:
            context_block = (
                f"CONTEXT:\n"
                f"Company: {scout_output.get('name', 'Unknown')}\n"
                f"One-line: {scout_output.get('one_line', 'N/A')}\n"
                f"Sector: {scout_output.get('sector', 'N/A')}\n"
                f"Problem: {scout_output.get('problem', 'N/A')}\n"
                f"Solution: {scout_output.get('solution', 'N/A')}\n"
                f"Target Users: {scout_output.get('target_users', 'N/A')}\n"
                f"Why Now: {scout_output.get('why_now', 'N/A')}"
            )

        risks_block = "\n".join(f"- {r}" for r in assumption_risks) if assumption_risks else "None identified"
        flags_block = "\n".join(f"- {f}" for f in diligence_red_flags) if diligence_red_flags else "None"

        portfolio_block = ""
        if portfolio_context and portfolio_context.get("total_portfolio_size", 0) > 0:
            portfolio_block = (
                f"\nPORTFOLIO CONTEXT:\n"
                f"Current portfolio: {portfolio_context.get('total_portfolio_size', 0)} companies\n"
                f"Sector concentration: {json.dumps(portfolio_context.get('sector_counts', {}))}\n"
            )

        score_variance_block = ""
        score_variance = review_output.get("score_variance")
        if score_variance:
            score_variance_block = f"\nSCORE VARIANCE ACROSS REVIEWERS:\n{json.dumps(score_variance)}\n"

        prompt = f"""You are a Senior Investment Partner at a venture capital firm making a final investment decision.

{context_block}

REVIEWER SCORES:
Market: {review_output.get('market_score', 0)}/10 - {score_reasoning.get('market_score', '')}
Product: {review_output.get('product_score', 0)}/10 - {score_reasoning.get('product_score', '')}
Technical: {review_output.get('technical_score', 0)}/10 - {score_reasoning.get('technical_score', '')}
Execution: {review_output.get('execution_score', 0)}/10 - {score_reasoning.get('execution_score', '')}
Defensibility: {review_output.get('defensibility_score', 'N/A')}/10 - {score_reasoning.get('defensibility_score', '')}
Verdict: {verdict}

ASSUMPTION RISKS:
{risks_block}

DILIGENCE RED FLAGS:
{flags_block}

QUALITATIVE ANALYSIS:
Team: {'; '.join(team_analysis) if team_analysis else '[MISSING]'}
Competition: {'; '.join(competition_analysis) if competition_analysis else '[MISSING]'}
Business Model: {'; '.join(business_model_analysis) if business_model_analysis else '[MISSING]'}
{portfolio_block}{score_variance_block}
TRIGGER REASON (why this needs LLM judgment):
{trigger_reason}

Output ONLY valid JSON: {{"decision": "YES"|"NO"|"MAYBE", "rationale": "...", "next_action": "...", "conviction_level": 1-10, "human_review_required": true|false}}"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a Senior Investment Partner making investment decisions. Be analytical, conservative, and data-driven."},
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
                max_completion_tokens=2048,
            )

            if response.usage:
                self._last_token_usage = {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                }

            content = response.choices[0].message.content
            if not content:
                self.logger.error("Empty LLM response; falling back to hardcoded")
                return self._decide_with_llm(
                    scout_output, review_output, assumption_risks,
                    trigger_reason=trigger_reason,
                )

            llm_result = json.loads(content)

            decision = llm_result.get("decision", "MAYBE")
            if decision not in ("YES", "NO", "MAYBE"):
                decision = "MAYBE"
            conviction = llm_result.get("conviction_level", 5)
            if not isinstance(conviction, int) or not (1 <= conviction <= 10):
                conviction = 5

            result = self._create_decision(
                decision=decision,
                confidence=conviction,
                rationale=llm_result.get("rationale", f"LLM decision for edge case: {trigger_reason}"),
                next_action=llm_result.get("next_action", next_actions.get("human_review_monitor", "Human review required")),
                human_review_required=llm_result.get("human_review_required", True),
                assumption_risks=assumption_risks,
            )
            result["llm_fallback_reason"] = trigger_reason
            return result

        except Exception as e:
            self.logger.error(f"LLM call failed: {e}; falling back to hardcoded")
            label = self._verdict_label(verdict)
            result = self._create_decision(
                decision="MAYBE",
                confidence=4,
                rationale=(
                    f"LLM call failed ({e}). Contradictory scores or critical assumptions detected. "
                    f"Average score: {avg_score:.1f}/10, Quality: {label}. Requires deeper analysis."
                ),
                next_action=next_actions.get("human_review_contradictions", "Human review required - analyze contradictions"),
                human_review_required=True,
                assumption_risks=assumption_risks,
            )
            result["llm_fallback_reason"] = trigger_reason
            return result
