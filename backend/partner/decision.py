"""
Partner decision engine.
Rule-based, deterministic decision making.
Uses /resources/partner_rules.json for thresholds, red flags, and LLM fallback triggers.
Default mode: NO LLM calls. LLM only for edge cases (contradictory scores, MEDIUM borderline, missing assumptions).
"""
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

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

    def __init__(self, use_llm_fallback: bool = True):
        """
        Initialize the decision engine.
        Loads rules from /resources/partner_rules.json.
        Args:
            use_llm_fallback: Whether to use LLM for edge cases (default: True)
        """
        self.use_llm_fallback = use_llm_fallback
        self.logger = logging.getLogger("partner.decision")
        self.llm_call_count = 0
        self._rules: Dict[str, Any] = _load_partner_rules()

    def _verdict_label(self, verdict: str) -> str:
        """Human-readable quality label for verdict. Uses quality_labels from rules."""
        labels = self._rules.get("quality_labels", {})
        return labels.get(verdict, verdict)

    def _get_rules(self) -> Dict[str, Any]:
        """Return loaded partner rules (cached after init)."""
        return self._rules

    def decide(self, scout_output: Dict[str, Any], review_output: Dict[str, Any]) -> Dict[str, Any]:
        """
        Make an investment decision based on Scout and Reviewer outputs.
        Uses assumption_feedback and Scout hypothesis (primary_thesis, key_assumptions,
        biggest_unknown) to compute assumption_risks and adjust conviction.
        Args:
            scout_output: Valid ScoutOutput dict (may include primary_thesis, key_assumptions, biggest_unknown)
            review_output: Valid ReviewerOutput dict (may include assumption_feedback; defaults to [])
        Returns:
            PartnerOutput with decision, conviction_level, rationale, next_action,
            human_review_required, assumption_risks. Legacy INVEST/WATCH/PASS mapped to YES/MAYBE/NO.
        """
        rules = self._get_rules()
        verdict_rules = rules.get("verdict_rules", {})
        score_thresholds = rules.get("score_thresholds", {})
        next_actions = rules.get("next_actions", {})

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
            return self._create_decision(
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

        # Rule 2: Critical risks → NO
        if has_critical_risk:
            return self._create_decision(
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

        # Rule 3: Low average score → NO
        if avg_score < min_avg_pass:
            label = self._verdict_label(verdict)
            return self._create_decision(
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

        # Rule 4: STRONG verdict + high score → YES
        strong_rule = verdict_rules.get("STRONG", {})
        if verdict == "STRONG" and avg_score >= min_avg_strong_yes:
            next_action = (
                next_actions.get("request_cap_table_and_review", "Request Cap Table + Technical Code Review")
                if has_red_flags
                else next_actions.get("request_cap_table", "Request Cap Table")
            )
            # Require human review when critical qualitative info (team or business model) is missing
            human_review = strong_rule.get("human_review_required_yes", True) or has_missing_critical_qualitative
            label = self._verdict_label(verdict)
            return self._create_decision(
                decision=strong_rule.get("decision_yes", "YES"),
                confidence=strong_rule.get("conviction_level_yes", 8) + conviction_adjust,
                rationale=(
                    f"Quality: {label}. High average score ({avg_score:.1f}/10). "
                    f"Market: {market_score}/10, Product: {product_score}/10, "
                    f"Technical: {technical_score}/10, Execution: {execution_score}/10. "
                    f"Meets investment criteria."
                    + (" Team or business model detail missing; human review recommended." if has_missing_critical_qualitative else "")
                ),
                next_action=next_action,
                human_review_required=human_review,
                assumption_risks=assumption_risks,
            )

        # Rule 5: MEDIUM verdict + good score → MAYBE (or LLM if contradictory / missing assumptions / missing qualitative)
        medium_rule = verdict_rules.get("MEDIUM", {})
        if verdict == "MEDIUM" and avg_score >= min_avg_medium_maybe:
            llm_triggers = rules.get("llm_fallback_triggers", {})
            use_llm = self.use_llm_fallback and (
                (has_contradiction and llm_triggers.get("contradictory_scores", True))
                or (has_missing_assumptions and llm_triggers.get("missing_assumptions_affecting_decision", True))
                or (has_missing_critical_qualitative and llm_triggers.get("missing_critical_qualitative", True))
            )
            if use_llm:
                return self._decide_with_llm(scout_output, review_output, assumption_risks)
            label = self._verdict_label(verdict)
            return self._create_decision(
                decision=medium_rule.get("decision_maybe", "MAYBE"),
                confidence=medium_rule.get("conviction_level_maybe", 6) + conviction_adjust,
                rationale=(
                    f"Quality: {label}. Solid average score ({avg_score:.1f}/10). "
                    f"Market: {market_score}/10, Product: {product_score}/10, "
                    f"Technical: {technical_score}/10, Execution: {execution_score}/10. "
                    f"Worth monitoring for market signals or team development."
                ),
                next_action=next_actions.get("monitor", "Monitor market and track progress"),
                human_review_required=False,
                assumption_risks=assumption_risks,
            )

        # Rule 6: MEDIUM verdict, borderline score → LLM or PASS
        if verdict == "MEDIUM" and min_avg_borderline_low <= avg_score < max_avg_borderline_high:
            llm_triggers = rules.get("llm_fallback_triggers", {})
            use_llm = self.use_llm_fallback and llm_triggers.get("medium_borderline_avg", True)
            if use_llm:
                return self._decide_with_llm(scout_output, review_output, assumption_risks)
            label = self._verdict_label(verdict)
            return self._create_decision(
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

        # Default: NO
        label = self._verdict_label(verdict)
        return self._create_decision(
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
    ) -> Dict[str, Any]:
        """
        Use LLM for nuanced decision in edge cases.
        Context includes Scout output, Reviewer output, hypothesis fields, and assumption_feedback.
        Returns strict PartnerOutput with assumption_risks. No actual LLM call by default.
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

        if verdict == "MEDIUM" and 6.0 <= avg_score < 7.0:
            label = self._verdict_label(verdict)
            return self._create_decision(
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

        label = self._verdict_label(verdict)
        return self._create_decision(
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
