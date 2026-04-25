"""
Partner decision engine.
Rule-based, deterministic decision making.
Uses versioned partner rules from resources/config (via policy_resolver).
Default mode: NO LLM calls. LLM only for edge cases (contradictory scores, MEDIUM borderline, missing assumptions).
"""
import os
import json
import logging
import re
from typing import Dict, Any, List, Optional, Tuple

from openai import OpenAI
from utils.prompt_version import hash_prompt
from utils.scoring import compute_overall_score


logger = logging.getLogger(__name__)

# ~6500 chars total user prompt budget (well under ~2000 tokens with system message)
_MAX_RULES_JSON_CHARS = 2800
_MAX_THESIS_MANDATE_CHARS = 3000


def _confidence_float_to_conviction_level(conf: Any) -> int:
    """Map model confidence in [0, 1] to conviction_level in [1, 10]."""
    try:
        c = float(conf)
    except (TypeError, ValueError):
        c = 0.5
    if c > 1.0:
        c = c / 10.0 if c <= 10.0 else 1.0
    c = max(0.0, min(1.0, c))
    return max(1, min(10, int(round(c * 9)) + 1))


def _recommendation_to_legacy_decision(recommendation: str) -> str:
    if recommendation == "INVEST":
        return "YES"
    if recommendation == "PASS":
        return "NO"
    return "MAYBE"


def _log_safe_single_line(blob: str, max_len: int = 6000) -> str:
    """Collapse newlines so one log record stays on one physical line (TTY readline consumers)."""
    s = " ".join((blob or "").replace("\r\n", "\n").replace("\r", "\n").split())
    if len(s) > max_len:
        return s[: max_len - 24] + " ...[truncated]"
    return s


def _partner_rules_json_for_prompt(rules: Dict[str, Any]) -> str:
    """Serialize partner rules; shrink if too large for the prompt token budget."""
    raw = json.dumps(rules, ensure_ascii=False, indent=2)
    if len(raw) <= _MAX_RULES_JSON_CHARS:
        return raw
    slim = {
        "version": rules.get("version"),
        "description": rules.get("description"),
        "score_thresholds": rules.get("score_thresholds"),
        "verdict_rules": rules.get("verdict_rules"),
        "llm_fallback_triggers": rules.get("llm_fallback_triggers"),
        "contradictory_scores": rules.get("contradictory_scores"),
        "next_actions": rules.get("next_actions"),
        "quality_labels": rules.get("quality_labels"),
    }
    raw2 = json.dumps(slim, ensure_ascii=False, indent=2)
    if len(raw2) <= _MAX_RULES_JSON_CHARS:
        return raw2 + "\n/* note: long keyword lists from full partner_rules were omitted */\n"
    return raw2[: _MAX_RULES_JSON_CHARS] + "\n/* truncated */\n"


def _parse_llm_json_object(content: str) -> Optional[Dict[str, Any]]:
    s = (content or "").strip()
    if not s:
        return None
    if s.startswith("```"):
        s = re.sub(r"^```(?:json)?\s*", "", s, flags=re.IGNORECASE).strip()
        s = re.sub(r"\s*```\s*$", "", s).strip()
    try:
        out = json.loads(s)
    except json.JSONDecodeError:
        # Best-effort salvage when model wraps JSON in prose.
        start = s.find("{")
        end = s.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                out = json.loads(s[start : end + 1])
            except json.JSONDecodeError:
                return None
        else:
            return None
    return out if isinstance(out, dict) else None


def _extract_chat_message_content(message: Any) -> str:
    """
    Extract text content from OpenAI chat completion message payloads.
    Supports plain string content and list-of-parts formats.
    """
    if message is None:
        return ""
    content = getattr(message, "content", None)
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, dict):
        text_val = content.get("text") or content.get("content") or content.get("value")
        if isinstance(text_val, dict):
            text_val = text_val.get("text") or text_val.get("value")
        if isinstance(text_val, str):
            return text_val.strip()
    if isinstance(content, list):
        chunks: List[str] = []
        for part in content:
            if isinstance(part, str):
                if part.strip():
                    chunks.append(part.strip())
                continue
            text_val = None
            if isinstance(part, dict):
                text_val = part.get("text") or part.get("content")
                if isinstance(text_val, dict):
                    text_val = text_val.get("value") or text_val.get("text")
            else:
                text_val = getattr(part, "text", None) or getattr(part, "content", None)
                if isinstance(text_val, dict):
                    text_val = text_val.get("value") or text_val.get("text")
            if isinstance(text_val, str) and text_val.strip():
                chunks.append(text_val.strip())
        return "\n".join(chunks).strip()
    parsed = getattr(message, "parsed", None)
    if isinstance(parsed, dict):
        try:
            return json.dumps(parsed, ensure_ascii=False)
        except Exception:
            pass
    refusal = getattr(message, "refusal", None)
    if isinstance(refusal, str) and refusal.strip():
        return refusal.strip()
    return ""


def _load_partner_rules() -> Dict[str, Any]:
    """
    Load partner rules via policy_resolver (resources/config/active.json + versioned JSON).
    """
    from core.policy_resolver import get_partner_rules

    return get_partner_rules()


class PartnerDecisionEngine:
    """
    Rule-based decision engine for Partner layer.
    Applies deterministic rules from versioned partner policy JSON to Reviewer outputs.
    Hypothesis-aware: uses assumption_feedback and Scout hypothesis fields to flag
    assumption_risks and adjust conviction. Conservative, opinionated, cost-aware.
    """

    def __init__(
        self,
        use_llm_fallback: bool = True,
        api_key: str = None,
        model: str = None,
        portfolio_store=None,
        tenant_user_id: str = "",
    ):
        """
        Initialize the decision engine.
        Loads rules via policy_resolver (active.json + versioned file).
        Args:
            use_llm_fallback: Whether to use LLM for edge cases (default: True)
            api_key: OpenAI API key for real LLM calls (falls back to env)
            model: Model name (falls back to env PARTNER_MODEL or gpt-5-nano)
            portfolio_store: Optional PortfolioStore for portfolio awareness
            tenant_user_id: Clerk user id for LLM / fallback logging (no implicit tenant).
        """
        self.use_llm_fallback = use_llm_fallback
        self.logger = logging.getLogger("partner.decision")
        self.tenant_user_id = (tenant_user_id or "").strip()
        self.llm_call_count = 0
        self._rules: Dict[str, Any] = _load_partner_rules()
        self.api_key = (api_key or os.getenv("OPENAI_API_KEY", "")).strip()
        self.model = model or os.getenv("PARTNER_MODEL", "gpt-5-nano")
        if self.api_key:
            self.client = OpenAI(api_key=self.api_key)
        else:
            self.client = None
        self._last_token_usage: Optional[Dict[str, int]] = None
        self.portfolio_store = portfolio_store
        self._llm_debug_logs = os.getenv("PARTNER_LLM_DEBUG_LOGS", "").strip().lower() in (
            "1",
            "true",
            "yes",
        )
        self._llm_stats: Dict[str, int] = {
            "fallback_invocations": 0,
            "request_errors": 0,
            "empty_content": 0,
            "retry_request_errors": 0,
            "rescue_request_errors": 0,
            "malformed_json": 0,
            "invalid_decision": 0,
            "generic_rationale_replaced": 0,
        }

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

    @staticmethod
    def _avg_score_and_dims(review_output: Dict[str, Any]) -> Tuple[float, int]:
        """Canonical mean of four core scores only (defensibility is separate)."""
        canonical = compute_overall_score(review_output)
        if canonical is None:
            return 0.0, 4
        return float(canonical), 4

    @staticmethod
    def _canonical_recommendation(avg_score: float) -> str:
        if avg_score >= 8.0:
            return "INVEST"
        if avg_score >= 6.0:
            return "MONITOR"
        return "PASS"

    def _enforce_canonical_recommendation(
        self,
        result: Dict[str, Any],
        avg_score: float,
        assumption_risks: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        forced = self._canonical_recommendation(avg_score)
        result["recommendation"] = forced
        result["decision"] = _recommendation_to_legacy_decision(forced)
        result["assumption_risks"] = list(assumption_risks or [])
        if forced == "PASS":
            result["next_action"] = self._next_action_for_llm_decision("PASS", self._get_rules().get("next_actions", {}))
        elif forced == "MONITOR":
            result["next_action"] = self._next_action_for_llm_decision("MONITOR", self._get_rules().get("next_actions", {}))
        else:
            result["next_action"] = self._next_action_for_llm_decision("INVEST", self._get_rules().get("next_actions", {}))
        return result

    @staticmethod
    def _optional_thesis_alignment_score(review_output: Dict[str, Any]) -> Optional[float]:
        if "thesis_alignment_score" not in review_output:
            return None
        raw = review_output.get("thesis_alignment_score")
        if raw is None:
            return None
        try:
            return float(raw)
        except (TypeError, ValueError):
            return None

    def _high_thesis_triggers_llm(
        self,
        review_output: Dict[str, Any],
        avg_score: float,
        min_avg_medium_maybe: float,
    ) -> bool:
        if avg_score < min_avg_medium_maybe:
            return False
        tas = self._optional_thesis_alignment_score(review_output)
        if tas is None:
            return False
        return tas >= 0.75

    @staticmethod
    def _is_medium_borderline_edge_case(
        avg_score: float,
        min_avg_borderline_low: float,
        max_avg_borderline_high: float,
        llm_triggers: Dict[str, Any],
    ) -> bool:
        """
        Trigger MEDIUM borderline LLM fallback only for genuine edge cases near the cutoff.
        Defaults to the upper 0.6-point band below max_avg_borderline_high (e.g., 6.4-7.0).
        """
        if not (min_avg_borderline_low <= avg_score < max_avg_borderline_high):
            return False
        edge_window = llm_triggers.get("medium_borderline_edge_window", 0.6)
        try:
            edge_window = float(edge_window)
        except (TypeError, ValueError):
            edge_window = 0.6
        edge_window = max(0.05, min(1.0, edge_window))
        return avg_score >= (max_avg_borderline_high - edge_window)

    @staticmethod
    def _is_low_score_near_threshold_edge_case(
        avg_score: float,
        min_avg_pass: float,
        llm_triggers: Dict[str, Any],
    ) -> bool:
        """
        Allow LLM fallback for MEDIUM decisions that are just below pass threshold.
        Default window is 0.25 below min_avg_pass (e.g., 5.75-6.0 when pass=6.0).
        """
        if avg_score >= min_avg_pass:
            return False
        near_window = llm_triggers.get("low_score_near_threshold_window", 0.25)
        try:
            near_window = float(near_window)
        except (TypeError, ValueError):
            near_window = 0.25
        near_window = max(0.05, min(0.6, near_window))
        return avg_score >= (min_avg_pass - near_window)

    def _build_narrative_from_inputs(
        self,
        scout_output: Dict[str, Any],
        review_output: Dict[str, Any],
    ) -> tuple:
        """
        Construct narrative fields from scout/review data for rule-based decisions.
        Returns: (thesis, why_this_matters, snapshot, market_insight, product_edge, traction_signals)
        """
        thesis = (scout_output.get("primary_thesis") or scout_output.get("one_line") or "").strip()
        why_this_matters = (scout_output.get("why_now") or "").strip()
        one_line = (scout_output.get("one_line") or "").strip()
        funding_stage = scout_output.get("funding_stage")
        overall_summary = (review_output.get("overall_summary") or "").strip()
        key_signal = overall_summary[:120] if overall_summary else None

        snapshot = {
            "one_liner": one_line,
            "stage": funding_stage,
            "key_signal": key_signal,
        }

        it = review_output.get("investment_thesis") or []
        if isinstance(it, list) and it:
            market_insight = it[0]
        else:
            sector = (scout_output.get("sector") or "").strip()
            market_insight = f"{sector} sector opportunity." if sector else "Market opportunity identified."

        solution = (scout_output.get("solution") or "").strip()
        comp = review_output.get("competition_analysis") or []
        if solution:
            product_edge = solution
        elif isinstance(comp, list) and comp:
            product_edge = comp[0]
        else:
            product_edge = "Product differentiation not assessed."

        traction_signals = None

        return thesis, why_this_matters, snapshot, market_insight, product_edge, traction_signals

    def _finalize_thesis_soft_and_log(
        self,
        result: Dict[str, Any],
        review_output: Dict[str, Any],
        scout_output: Dict[str, Any],
        avg_score: float,
        avg_dims: int,
    ) -> Dict[str, Any]:
        thesis_adjusted = False
        tas = self._optional_thesis_alignment_score(review_output)
        if result.get("recommendation") == "PASS" and tas is not None and tas < 0.3:
            r = (result.get("decision_rationale") or "").rstrip()
            if "Clear thesis mismatch." not in r:
                result["decision_rationale"] = r + " Clear thesis mismatch."
            thesis_adjusted = True
        elif tas is not None and tas < 0.4:
            r = (result.get("decision_rationale") or "").rstrip()
            if "Low thesis alignment." not in r:
                result["decision_rationale"] = r + " Low thesis alignment."
            thesis_adjusted = True
        self.logger.info(
            "partner_decide company=%s avg_score=%.2f avg_dims=%d thesis_soft=%s final=%s",
            scout_output.get("name", ""),
            avg_score,
            avg_dims,
            thesis_adjusted,
            result.get("recommendation"),
        )
        return result

    def _record_llm_stat(self, key: str) -> None:
        self._llm_stats[key] = int(self._llm_stats.get(key, 0)) + 1

    def decide(
        self,
        scout_output: Dict[str, Any],
        review_output: Dict[str, Any],
        context_memo: str = "",
        fund_thesis: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Make an investment decision based on Scout and Reviewer outputs.
        Uses assumption_feedback and Scout hypothesis (primary_thesis, key_assumptions,
        biggest_unknown) to compute assumption_risks and adjust conviction.
        Args:
            scout_output: Valid ScoutOutput dict (may include primary_thesis, key_assumptions, biggest_unknown, sector, funding_stage)
            review_output: Valid ReviewerOutput dict (may include assumption_feedback; defaults to [])
            context_memo: Optional pre-decision memo text for LLM context
        Returns:
            Partner output dict with decision, conviction_level, rationale, next_action,
            human_review_required, assumption_risks.
        """
        rules = self._get_rules()
        verdict_rules = rules.get("verdict_rules", {})
        score_thresholds = rules.get("score_thresholds", {})
        next_actions = rules.get("next_actions", {})

        portfolio_context = self._get_portfolio_context() if self.portfolio_store else {}
        thesis_block = ""
        if fund_thesis:
            pj = fund_thesis.get("parsed_json") or {}
            thesis_block = (
                "\nFUND THESIS MANDATE:\n"
                f"version_id: {fund_thesis.get('version_id', '')}\n"
                f"{json.dumps(pj, ensure_ascii=False)[:8000]}\n"
            )
        try:
            from core.fund_thesis_resolver import format_fund_thesis_context_for_prompt

            resource_ctx = format_fund_thesis_context_for_prompt()
            if resource_ctx:
                thesis_block = (thesis_block or "") + resource_ctx
        except Exception:
            pass

        market_score = review_output.get("market_score", 0)
        product_score = review_output.get("product_score", 0)
        technical_score = review_output.get("technical_score", 0)
        execution_score = review_output.get("execution_score", 0)
        _derived = review_output.get("derived_verdict")
        if (
            isinstance(_derived, str)
            and _derived.strip()
            and _derived.strip() in ("STRONG", "MEDIUM", "WEAK")
        ):
            effective_verdict = _derived.strip()
            verdict_source = "derived"
        else:
            effective_verdict = review_output.get("verdict", "WEAK")
            verdict_source = "original"
        self.logger.info(
            "partner_decide verdict_source=%s effective_verdict=%s",
            verdict_source,
            effective_verdict,
        )
        key_risks = review_output.get("key_risks", [])
        assumption_feedback: List[str] = review_output.get("assumption_feedback") or []

        avg_score, avg_dims = self._avg_score_and_dims(review_output)

        # Grey Zone: compute once here; used in MEDIUM rules below
        llm_triggers_global = rules.get("llm_fallback_triggers", {})
        grey_zone_score = review_output.get("confidence_adjusted_score")
        if grey_zone_score is None:
            grey_zone_score = avg_score
        grey_zone_min = score_thresholds.get("grey_zone_min", 6.5)
        grey_zone_max = score_thresholds.get("grey_zone_max", 7.5)
        grey_zone_active = (
            llm_triggers_global.get("grey_zone_deep_dive", False)
            and grey_zone_min <= grey_zone_score <= grey_zone_max
        )

        min_avg_pass = score_thresholds.get("min_avg_pass", 6.0)
        min_avg_strong_yes = score_thresholds.get("min_avg_strong_yes", 8.0)
        min_avg_medium_maybe = score_thresholds.get("min_avg_medium_maybe", 7.0)
        min_avg_borderline_low = score_thresholds.get("min_avg_borderline_low", 6.0)
        max_avg_borderline_high = score_thresholds.get("max_avg_borderline_high", 7.0)

        assumption_risks = self._compute_assumption_risks(
            scout_output, review_output, assumption_feedback
        )
        conviction_adjust = -1 if assumption_risks else 0

        # Narrative fields computed once from inputs — reused by all rule branches
        n_thesis, n_why, n_snapshot, n_market, n_product, n_traction = (
            self._build_narrative_from_inputs(scout_output, review_output)
        )
        # Merged risks: key_risks + assumption_risks, deduplicated, max 5
        merged_risks: List[str] = list(dict.fromkeys(
            (key_risks or []) + assumption_risks
        ))[:5]

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

        # Rule 1: WEAK verdict → PASS
        weak_rule = verdict_rules.get("WEAK", {})
        if effective_verdict == "WEAK":
            label = self._verdict_label(effective_verdict)
            result = self._create_decision(
                recommendation="PASS",
                conviction=weak_rule.get("conviction_level", 9),
                decision_rationale=(
                    f"Quality assessment: {label}. Average score: {avg_score:.1f}/10. "
                    f"Not suitable for investment consideration."
                ),
                next_action=weak_rule.get("next_action", "Pass - Market too crowded / Low quality"),
                human_review_required=weak_rule.get("human_review_required", False),
                thesis=n_thesis,
                why_this_matters=n_why,
                snapshot=n_snapshot,
                market_insight=n_market,
                product_edge=n_product,
                traction_signals=n_traction,
                risks=merged_risks,
            )
            result = self._enforce_canonical_recommendation(result, avg_score, assumption_risks)
            return self._finalize_thesis_soft_and_log(
                result, review_output, scout_output, avg_score, avg_dims
            )

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

        # Rule 2: Critical risks → PASS
        if has_critical_risk:
            result = self._create_decision(
                recommendation="PASS",
                conviction=8 + conviction_adjust,
                decision_rationale=(
                    f"Critical risks identified (regulatory or execution impossibility). "
                    f"Average score: {avg_score:.1f}/10. Risk too high for investment."
                ),
                next_action=next_actions.get("critical_risks", "Pass - Critical risks too high"),
                human_review_required=False,
                thesis=n_thesis,
                why_this_matters=n_why,
                snapshot=n_snapshot,
                market_insight=n_market,
                product_edge=n_product,
                traction_signals=n_traction,
                risks=merged_risks,
            )
            result = self._enforce_canonical_recommendation(result, avg_score, assumption_risks)
            return self._finalize_thesis_soft_and_log(
                result, review_output, scout_output, avg_score, avg_dims
            )

        # Rule 3: Low average score → PASS
        if avg_score < min_avg_pass:
            llm_triggers = rules.get("llm_fallback_triggers", {})
            low_score_edge_case = (
                effective_verdict == "MEDIUM"
                and llm_triggers.get("low_score_near_threshold", True)
                and self._is_low_score_near_threshold_edge_case(
                    avg_score=avg_score,
                    min_avg_pass=min_avg_pass,
                    llm_triggers=llm_triggers,
                )
            )
            if self.use_llm_fallback and low_score_edge_case:
                trigger_reason = "MEDIUM verdict slightly below pass threshold"
                result = self._decide_with_llm(
                    scout_output,
                    review_output,
                    assumption_risks,
                    trigger_reason=trigger_reason,
                    context_memo=context_memo,
                    portfolio_context=portfolio_context,
                    thesis_block=thesis_block,
                    avg_score=avg_score,
                    avg_dims=avg_dims,
                )
                result = self._enforce_canonical_recommendation(result, avg_score, assumption_risks)
                return self._finalize_thesis_soft_and_log(
                    result, review_output, scout_output, avg_score, avg_dims
                )
            label = self._verdict_label(effective_verdict)
            result = self._create_decision(
                recommendation="PASS",
                conviction=7 + conviction_adjust,
                decision_rationale=(
                    f"Average score {avg_score:.1f}/10 below threshold ({min_avg_pass}). "
                    f"Quality: {label}. Insufficient quality for investment."
                ),
                next_action=next_actions.get("low_scores", "Pass - Low scores"),
                human_review_required=False,
                thesis=n_thesis,
                why_this_matters=n_why,
                snapshot=n_snapshot,
                market_insight=n_market,
                product_edge=n_product,
                traction_signals=n_traction,
                risks=merged_risks,
            )
            result = self._enforce_canonical_recommendation(result, avg_score, assumption_risks)
            return self._finalize_thesis_soft_and_log(
                result, review_output, scout_output, avg_score, avg_dims
            )

        # Rule 4: STRONG verdict, pass bar met but below YES bar → MONITOR
        strong_rule = verdict_rules.get("STRONG", {})
        if (
            effective_verdict == "STRONG"
            and min_avg_pass <= avg_score < min_avg_strong_yes
        ):
            next_act = strong_rule.get(
                "next_action_below_strong_yes_bar",
                next_actions.get("monitor", "Monitor market and track progress"),
            )
            label = self._verdict_label(effective_verdict)
            rationale_parts = (
                f"Quality: {label}. Average score ({avg_score:.1f}/10) meets the pass bar "
                f"({min_avg_pass}) but is below the strong-YES bar ({min_avg_strong_yes}). "
                f"Market: {market_score}/10, Product: {product_score}/10, "
                f"Technical: {technical_score}/10, Execution: {execution_score}/10. "
                f"Worth monitoring while execution and thesis signals mature."
            )
            if portfolio_context and portfolio_context.get("sector_counts", {}).get(
                startup_sector, 0
            ) >= 3:
                rationale_parts += " sector_concentration_risk"
            result = self._create_decision(
                recommendation="MONITOR",
                conviction=strong_rule.get("conviction_level_below_strong_yes_bar", 6) + conviction_adjust,
                decision_rationale=rationale_parts,
                next_action=next_act,
                human_review_required=strong_rule.get("human_review_required_below_strong_yes_bar", False),
                thesis=n_thesis,
                why_this_matters=n_why,
                snapshot=n_snapshot,
                market_insight=n_market,
                product_edge=n_product,
                traction_signals=n_traction,
                risks=merged_risks,
            )
            result = self._enforce_canonical_recommendation(result, avg_score, assumption_risks)
            return self._finalize_thesis_soft_and_log(
                result, review_output, scout_output, avg_score, avg_dims
            )

        # Rule 5: STRONG verdict + high score → INVEST
        if effective_verdict == "STRONG" and avg_score >= min_avg_strong_yes:
            next_action = (
                next_actions.get("request_cap_table_and_review", "Request Cap Table + Technical Code Review")
                if has_red_flags
                else next_actions.get("request_cap_table", "Request Cap Table")
            )
            human_review = strong_rule.get("human_review_required_yes", True) or has_missing_critical_qualitative
            label = self._verdict_label(effective_verdict)
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
                recommendation="INVEST",
                conviction=strong_rule.get("conviction_level_yes", 8) + conviction_adjust,
                decision_rationale=rationale_parts,
                next_action=next_action,
                human_review_required=human_review,
                thesis=n_thesis,
                why_this_matters=n_why,
                snapshot=n_snapshot,
                market_insight=n_market,
                product_edge=n_product,
                traction_signals=n_traction,
                risks=merged_risks,
            )
            result = self._enforce_canonical_recommendation(result, avg_score, assumption_risks)
            return self._finalize_thesis_soft_and_log(
                result, review_output, scout_output, avg_score, avg_dims
            )

        # Check reviewer disagreement for LLM trigger
        reviewer_disagreement = review_output.get("reviewer_disagreement", False)

        # Rule 6: MEDIUM verdict + good score → MONITOR (or LLM if contradictory / missing assumptions / missing qualitative / disagreement)
        medium_rule = verdict_rules.get("MEDIUM", {})
        if effective_verdict == "MEDIUM" and avg_score >= min_avg_medium_maybe:
            llm_triggers = rules.get("llm_fallback_triggers", {})
            trigger_reason = ""
            if grey_zone_active:
                trigger_reason = (
                    f"Grey zone deep dive: S_adj={grey_zone_score:.2f} in "
                    f"[{grey_zone_min}, {grey_zone_max}]"
                )
            elif has_contradiction and llm_triggers.get("contradictory_scores", True):
                trigger_reason = "Contradictory scores detected (gap >= threshold)"
            elif has_missing_assumptions and llm_triggers.get("missing_assumptions_affecting_decision", True):
                trigger_reason = "Missing assumptions affecting decision"
            elif has_missing_critical_qualitative and llm_triggers.get("missing_critical_qualitative", True):
                trigger_reason = "Missing critical qualitative data (team/business model)"
            elif reviewer_disagreement and llm_triggers.get("reviewer_disagreement", False):
                trigger_reason = "Reviewer disagreement detected"
            elif self._high_thesis_triggers_llm(
                review_output, avg_score, min_avg_medium_maybe
            ):
                trigger_reason = "High thesis alignment with solid average — extended partner review"
            use_llm = self.use_llm_fallback and bool(trigger_reason)
            if use_llm:
                result = self._decide_with_llm(
                    scout_output,
                    review_output,
                    assumption_risks,
                    trigger_reason=trigger_reason,
                    context_memo=context_memo,
                    portfolio_context=portfolio_context,
                    thesis_block=thesis_block,
                    avg_score=avg_score,
                    avg_dims=avg_dims,
                )
                result = self._enforce_canonical_recommendation(result, avg_score, assumption_risks)
                return self._finalize_thesis_soft_and_log(
                    result, review_output, scout_output, avg_score, avg_dims
                )
            label = self._verdict_label(effective_verdict)
            rationale_text = (
                f"Quality: {label}. Solid average score ({avg_score:.1f}/10). "
                f"Market: {market_score}/10, Product: {product_score}/10, "
                f"Technical: {technical_score}/10, Execution: {execution_score}/10. "
                f"Worth monitoring for market signals or team development."
            )
            if portfolio_context and portfolio_context.get("sector_counts", {}).get(startup_sector, 0) >= 3:
                rationale_text += " sector_concentration_risk"
            result = self._create_decision(
                recommendation="MONITOR",
                conviction=medium_rule.get("conviction_level_maybe", 6) + conviction_adjust,
                decision_rationale=rationale_text,
                next_action=next_actions.get("monitor", "Monitor market and track progress"),
                human_review_required=False,
                thesis=n_thesis,
                why_this_matters=n_why,
                snapshot=n_snapshot,
                market_insight=n_market,
                product_edge=n_product,
                traction_signals=n_traction,
                risks=merged_risks,
            )
            result = self._enforce_canonical_recommendation(result, avg_score, assumption_risks)
            return self._finalize_thesis_soft_and_log(
                result, review_output, scout_output, avg_score, avg_dims
            )

        # Rule 7: MEDIUM verdict, borderline score → LLM or deterministic MONITOR
        if effective_verdict == "MEDIUM" and min_avg_borderline_low <= avg_score < max_avg_borderline_high:
            llm_triggers = rules.get("llm_fallback_triggers", {})
            is_edge_case = self._is_medium_borderline_edge_case(
                avg_score=avg_score,
                min_avg_borderline_low=min_avg_borderline_low,
                max_avg_borderline_high=max_avg_borderline_high,
                llm_triggers=llm_triggers,
            )
            use_llm = (
                self.use_llm_fallback
                and (llm_triggers.get("medium_borderline_avg", True) and is_edge_case or grey_zone_active)
            )
            if use_llm:
                trigger_reason = (
                    f"Grey zone deep dive: S_adj={grey_zone_score:.2f} in [{grey_zone_min}, {grey_zone_max}]"
                    if grey_zone_active
                    else "MEDIUM verdict with borderline average score"
                )
                result = self._decide_with_llm(
                    scout_output,
                    review_output,
                    assumption_risks,
                    trigger_reason=trigger_reason,
                    context_memo=context_memo,
                    portfolio_context=portfolio_context,
                    thesis_block=thesis_block,
                    avg_score=avg_score,
                    avg_dims=avg_dims,
                )
                result = self._enforce_canonical_recommendation(result, avg_score, assumption_risks)
                return self._finalize_thesis_soft_and_log(
                    result, review_output, scout_output, avg_score, avg_dims
                )
            label = self._verdict_label(effective_verdict)
            result = self._create_decision(
                recommendation="MONITOR",
                conviction=medium_rule.get("conviction_level_borderline", 5) + conviction_adjust,
                decision_rationale=(
                    f"Quality: {label}. Average score ({avg_score:.1f}/10) is in the borderline band "
                    f"({min_avg_borderline_low}-{max_avg_borderline_high}) — below the watchlist "
                    f"threshold ({min_avg_medium_maybe}) but at or above the pass bar ({min_avg_pass}). "
                    f"Defaulting to monitor rather than a hard pass."
                ),
                next_action=medium_rule.get(
                    "next_action_borderline",
                    next_actions.get("monitor", "Monitor market and track progress"),
                ),
                human_review_required=False,
                thesis=n_thesis,
                why_this_matters=n_why,
                snapshot=n_snapshot,
                market_insight=n_market,
                product_edge=n_product,
                traction_signals=n_traction,
                risks=merged_risks,
            )
            result = self._enforce_canonical_recommendation(result, avg_score, assumption_risks)
            return self._finalize_thesis_soft_and_log(
                result, review_output, scout_output, avg_score, avg_dims
            )

        # Default: PASS
        label = self._verdict_label(effective_verdict)
        result = self._create_decision(
            recommendation="PASS",
            conviction=6 + conviction_adjust,
            decision_rationale=(
                f"Does not meet investment criteria. Quality: {label}. "
                f"Average score: {avg_score:.1f}/10."
            ),
            next_action=next_actions.get("default_no", "Pass - Does not meet criteria"),
            human_review_required=False,
            thesis=n_thesis,
            why_this_matters=n_why,
            snapshot=n_snapshot,
            market_insight=n_market,
            product_edge=n_product,
            traction_signals=n_traction,
            risks=merged_risks,
        )
        result = self._enforce_canonical_recommendation(result, avg_score, assumption_risks)
        return self._finalize_thesis_soft_and_log(
            result, review_output, scout_output, avg_score, avg_dims
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
        """
        True when Reviewer feedback (or non-scout risk lines) flag assumptions that
        warrant partner escalation. Scout-only `biggest_unknown` is kept in
        assumption_risks for transparency but does not alone trigger LLM.
        """
        if not assumption_risks:
            return False

        def _is_scout_biggest_unknown_line(r: str) -> bool:
            return (r or "").strip().lower().startswith("biggest unknown:")

        if any(not _is_scout_biggest_unknown_line(r) for r in assumption_risks):
            return True

        if not assumption_feedback:
            return False

        keywords = rules.get(
            "assumption_risk_keywords",
            [
                "critical unknown",
                "unvalidated assumption",
                "weak assumption",
                "could invalidate",
                "unresolved",
                "missing validation",
            ],
        )
        feedback_lower = [f.lower() for f in assumption_feedback]
        for i, fb in enumerate(assumption_feedback):
            if any(kw in feedback_lower[i] for kw in keywords):
                return True
        for fb in assumption_feedback:
            if any(w in fb.lower() for w in ("unknown", "unclear", "unvalidated", "risk")):
                return True
        return False

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

    def _extract_step_items(self, text: str) -> List[str]:
        """Best-effort extraction of checklist items from variable LLM text formats."""
        s = (text or "").strip()
        if not s:
            return []

        # Numbered markers like: "1) ... 2) ..." or "1. ... 2. ..."
        marker = re.compile(r"(?:^|\s)(\d+[\)\.])\s+")
        matches = list(marker.finditer(s))
        if len(matches) >= 2:
            items: List[str] = []
            for i, m in enumerate(matches):
                start = m.end()
                end = matches[i + 1].start() if i + 1 < len(matches) else len(s)
                item = s[start:end].strip(" ;\n\t")
                if item:
                    items.append(item)
            if items:
                return items[:10]

        # Bullet-style inline separators: " - item - item"
        if " - " in s:
            parts = [p.strip(" ;\n\t-") for p in re.split(r"\s-\s+", s) if p.strip()]
            if len(parts) > 1:
                return parts[:10]

        # Semicolon-separated checklist
        if ";" in s:
            parts = [p.strip(" ;\n\t") for p in s.split(";") if p.strip()]
            if len(parts) > 1:
                return parts[:10]

        # Line-based bullets/numbers
        lines = [ln.strip() for ln in s.splitlines() if ln.strip()]
        if len(lines) > 1:
            cleaned: List[str] = []
            for ln in lines:
                cleaned_item = re.sub(r"^[-*•]\s+", "", ln)
                cleaned_item = re.sub(r"^\d+[\)\.]\s+", "", cleaned_item)
                cleaned_item = cleaned_item.strip()
                if cleaned_item:
                    cleaned.append(cleaned_item)
            if cleaned:
                return cleaned[:10]

        return []

    def _normalize_next_action(self, next_action: str) -> str:
        """
        Normalize next_action to a numbered checklist when multiple actionable
        steps are present. Keep single-paragraph guidance unchanged.
        """
        raw = (next_action or "").strip()
        if not raw:
            return ""
        items = self._extract_step_items(raw)
        if not items:
            return raw
        return "\n".join(f"{i + 1}) {item}" for i, item in enumerate(items))

    def _create_decision(
        self,
        recommendation: Optional[str] = None,
        conviction: Optional[int] = None,
        decision_rationale: Optional[str] = None,
        next_action: str = "",
        human_review_required: bool = False,
        thesis: str = "",
        why_this_matters: str = "",
        snapshot: Optional[Dict[str, Any]] = None,
        market_insight: str = "",
        product_edge: str = "",
        traction_signals: Optional[str] = None,
        risks: Optional[List[str]] = None,
        **legacy_kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Build a decision dict conforming to the new partner schema.
        Conviction (1–10) is normalized to confidence (0.0–1.0).
        """
        legacy_decision = legacy_kwargs.get("decision")
        legacy_confidence = legacy_kwargs.get("confidence")
        legacy_rationale = legacy_kwargs.get("rationale")
        if recommendation is None and isinstance(legacy_decision, str):
            recommendation = {"YES": "INVEST", "NO": "PASS", "MAYBE": "MONITOR"}.get(
                legacy_decision.strip().upper(), "MONITOR"
            )
        recommendation = recommendation or "MONITOR"
        if conviction is None:
            conviction = int(legacy_confidence) if isinstance(legacy_confidence, (int, float)) else 5
        if decision_rationale is None and isinstance(legacy_rationale, str):
            decision_rationale = legacy_rationale
        decision_rationale = decision_rationale or ""
        snapshot = snapshot or {"one_liner": "", "stage": None, "key_signal": None}
        risks = risks or legacy_kwargs.get("assumption_risks") or []
        conviction_clamped = max(1, min(10, int(conviction)))
        return {
            "recommendation": recommendation,
            "confidence": round(conviction_clamped / 10.0, 2),
            "decision": _recommendation_to_legacy_decision(recommendation),
            "conviction_level": conviction_clamped,
            "thesis": thesis,
            "why_this_matters": why_this_matters,
            "snapshot": snapshot,
            "market_insight": market_insight,
            "product_edge": product_edge,
            "traction_signals": traction_signals,
            "risks": risks[:5] if risks else [],
            "decision_rationale": decision_rationale,
            "rationale": decision_rationale,
            "next_action": self._normalize_next_action(next_action),
            "human_review_required": human_review_required,
        }

    def _next_action_for_llm_decision(self, recommendation: str, next_actions: Dict[str, Any]) -> str:
        if recommendation == "INVEST":
            return next_actions.get("request_cap_table", "Request Cap Table")
        if recommendation == "PASS":
            return next_actions.get("default_no", "Pass - Does not meet criteria")
        return next_actions.get("human_review_monitor", "Human review required - monitor closely")

    def _compact_llm_rescue_call(
        self,
        uid_log: str,
        model: str,
        scout_output: Dict[str, Any],
        review_output: Dict[str, Any],
        trigger_reason: str,
    ) -> str:
        """
        Final fallback call with a tiny prompt to avoid large-context/formatting failures.
        Returns raw model text content (possibly empty).
        """
        compact_prompt = (
            "Return ONLY a JSON object with keys: recommendation, confidence, decision_rationale.\n"
            "recommendation must be one of INVEST/PASS/MONITOR.\n"
            "confidence must be a float in [0,1].\n"
            "decision_rationale must be a non-empty string.\n\n"
            f"company={scout_output.get('name', 'Unknown')}\n"
            f"verdict={review_output.get('verdict', 'MEDIUM')}\n"
            f"scores={{market:{review_output.get('market_score', 0)},product:{review_output.get('product_score', 0)},"
            f"technical:{review_output.get('technical_score', 0)},execution:{review_output.get('execution_score', 0)},"
            f"defensibility:{review_output.get('defensibility_score', 'N/A')}}}\n"
            f"trigger={trigger_reason}\n"
        )
        rescue_response = self.client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a strict JSON generator."},
                {"role": "user", "content": compact_prompt},
            ],
            max_completion_tokens=2048,
        )
        rescue_finish_reason = None
        try:
            rescue_finish_reason = rescue_response.choices[0].finish_reason
        except Exception:
            rescue_finish_reason = None
        self.logger.info(
            "[PARTNER] partner_llm_fallback user_id=%s compact_rescue_finish_reason=%s",
            uid_log,
            rescue_finish_reason,
        )
        if self._llm_debug_logs:
            rescue_raw = (
                rescue_response.model_dump_json()
                if hasattr(rescue_response, "model_dump_json")
                else repr(rescue_response)
            )
            self.logger.info(
                "[PARTNER] partner_llm_fallback user_id=%s compact_rescue_raw_api_response=%s",
                uid_log,
                _log_safe_single_line(rescue_raw),
            )
        try:
            return _extract_chat_message_content(rescue_response.choices[0].message)
        except (IndexError, AttributeError):
            return ""

    def _decide_with_llm(
        self,
        scout_output: Dict[str, Any],
        review_output: Dict[str, Any],
        assumption_risks: List[str],
        trigger_reason: str = "",
        context_memo: str = "",
        portfolio_context: dict = None,
        thesis_block: str = "",
        *,
        avg_score: float = 0.0,
        avg_dims: int = 4,
    ) -> Dict[str, Any]:
        """
        LLM path when rule engine defers (edge cases). Uses OpenAI chat.completions with JSON output.
        On missing client, empty/invalid response, or errors: MAYBE, conviction 1 (confidence 0.0), safe rationale.
        """
        del context_memo  # omitted from prompt to respect token budget; rule path unchanged
        del portfolio_context
        del avg_score, avg_dims  # caller uses for post-LLM finalize + logging only

        self.llm_call_count += 1
        self._record_llm_stat("fallback_invocations")
        uid_log = self.tenant_user_id[:24] if self.tenant_user_id else ""
        self.logger.warning(
            "[PARTNER] partner_llm_fallback user_id=%s call#=%s company=%s trigger=%s",
            uid_log,
            self.llm_call_count,
            scout_output.get("name", "Unknown"),
            trigger_reason[:120] if trigger_reason else "",
        )

        rules = self._get_rules()
        next_actions = rules.get("next_actions", {})
        verdict = review_output.get("verdict", "MEDIUM")
        score_reasoning = review_output.get("score_reasoning") or {}

        def _failure_outcome(prompt_snapshot: str, rationale: str) -> Dict[str, Any]:
            n_t, n_w, n_s, n_m, n_p, n_tr = self._build_narrative_from_inputs(
                scout_output, review_output
            )
            f_risks: List[str] = list(dict.fromkeys(
                (review_output.get("key_risks") or []) + assumption_risks
            ))[:5]
            result = self._create_decision(
                recommendation="MONITOR",
                conviction=1,
                decision_rationale=rationale,
                next_action=next_actions.get(
                    "human_review_contradictions",
                    "Human review required - analyze contradictions",
                ),
                human_review_required=True,
                thesis=n_t,
                why_this_matters=n_w,
                snapshot=n_s,
                market_insight=n_m,
                product_edge=n_p,
                traction_signals=n_tr,
                risks=f_risks,
            )
            result["llm_fallback_reason"] = trigger_reason
            result["prompt_version"] = hash_prompt(prompt_snapshot) if prompt_snapshot else None
            self.logger.warning(
                "[PARTNER] partner_llm_fallback_metrics user_id=%s stats=%s",
                uid_log,
                json.dumps(self._llm_stats, sort_keys=True),
            )
            return result

        def _synthesize_rationale() -> str:
            """Build a real reasoning rationale from available scores and data when LLM fails."""
            name = scout_output.get("name", "Unknown")
            m = review_output.get("market_score", 0)
            p = review_output.get("product_score", 0)
            t = review_output.get("technical_score", 0)
            e = review_output.get("execution_score", 0)
            avg, _ = self._avg_score_and_dims(review_output)
            v = review_output.get("derived_verdict") or review_output.get("verdict", "MEDIUM")
            parts = [
                f"{name} received a {v} verdict with an average score of {avg:.1f}/10",
                f"(Market: {m}, Product: {p}, Technical: {t}, Execution: {e}).",
            ]
            risks = review_output.get("key_risks") or []
            if risks:
                parts.append(f"Key risks: {'; '.join(risks[:3])}.")
            if assumption_risks:
                parts.append(f"Assumption concerns: {'; '.join(assumption_risks[:2])}.")
            parts.append(
                f"The LLM partner analysis was unable to render a full response (trigger: {trigger_reason}). "
                "Deferring to human review for a definitive assessment."
            )
            return " ".join(parts)

        if self.client is None:
            self.logger.warning(
                "[PARTNER] partner_llm_fallback user_id=%s no OpenAI client; skipping model call",
                uid_log,
            )
            return _failure_outcome(
                "",
                _synthesize_rationale(),
            )

        try:
            from core.policy_resolver import get_partner_rules

            partner_rules_payload = get_partner_rules()
        except Exception as e:
            self.logger.warning("[PARTNER] partner_llm_fallback user_id=%s could not load partner_rules: %s", uid_log, e)
            partner_rules_payload = rules

        rules_json = _partner_rules_json_for_prompt(
            partner_rules_payload if isinstance(partner_rules_payload, dict) else {}
        )
        tb = (thesis_block or "").strip()
        if len(tb) > _MAX_THESIS_MANDATE_CHARS:
            tb = tb[: _MAX_THESIS_MANDATE_CHARS - 30] + "\n...(truncated)\n"
        thesis_section = f"FUND THESIS MANDATE (and resource lens if present):\n{tb}\n\n" if tb else ""

        sr_json = json.dumps(score_reasoning, ensure_ascii=False)
        if len(sr_json) > 3500:
            sr_json = sr_json[:3500] + "...(truncated)"

        ds = review_output.get("defensibility_score")
        ds_disp = ds if ds is not None else "N/A"

        user_prompt = f"""{thesis_section}STARTUP
display_name: {scout_output.get('name', 'Unknown')}
sector: {scout_output.get('sector', 'N/A')}
stage (funding): {scout_output.get('funding_stage', 'N/A')}
one_line: {scout_output.get('one_line', 'N/A')}
primary_thesis: {scout_output.get('primary_thesis', 'N/A')}
why_now: {scout_output.get('why_now', 'N/A')}

REVIEWER OUTPUT
verdict: {verdict}
market_score: {review_output.get('market_score', 0)}/10
product_score: {review_output.get('product_score', 0)}/10
technical_score: {review_output.get('technical_score', 0)}/10
execution_score: {review_output.get('execution_score', 0)}/10
defensibility_score: {ds_disp}/10
score_reasoning (full JSON): {sr_json}

THESIS ALIGNMENT (from review)
thesis_alignment_score: {review_output.get('thesis_alignment_score')}
thesis_matches_fund: {review_output.get('thesis_matches_fund')}
thesis_fit_points: {json.dumps(review_output.get('thesis_fit_points') or [], ensure_ascii=False)}
thesis_deviation_points: {json.dumps(review_output.get('thesis_deviation_points') or [], ensure_ascii=False)}

PARTNER_RULES_JSON (fund criteria; reason strictly against this policy)
{rules_json}

TRIGGER REASON (why the rule engine deferred)
{trigger_reason}

Return ONLY a single valid JSON object with exactly these keys:
{{
  "recommendation": "INVEST" | "PASS" | "MONITOR",
  "confidence": <float 0.0-1.0>,
  "thesis": "<investment thesis — 1 sentence>",
  "why_this_matters": "<market timing or structural shift — 1 sentence>",
  "snapshot": {{"one_liner": "<company one-liner>", "stage": "<funding stage or null>", "key_signal": "<top signal or null>"}},
  "market_insight": "<key market dynamic — 1 sentence>",
  "product_edge": "<meaningful differentiation or lack thereof — 1 sentence>",
  "traction_signals": "<traction evidence or null>",
  "risks": ["<risk 1>", "<risk 2>", "<risk 3>"],
  "decision_rationale": "<2-3 sentences citing dimension scores and thesis fit>",
  "next_action": "<specific next step for the team>",
  "human_review_required": <true|false>
}}
No markdown. No extra fields. Strictly under 350 words total information density. Be opinionated.
"""

        system_prompt = (
            "You are a Senior Investment Partner. Edge cases only: the deterministic rule path already passed. "
            "Apply PARTNER_RULES_JSON strictly. Output only valid JSON per the user instructions."
        )
        prompt_for_hash = system_prompt + "\n\n" + user_prompt

        try:
            self.logger.warning(
                "[PARTNER] partner_llm_fallback user_id=%s model=%s request_started prompt_chars=%s",
                uid_log,
                self.model,
                len(prompt_for_hash),
            )
            if self._llm_debug_logs:
                self.logger.warning(
                    "[PARTNER] partner_llm_fallback user_id=%s request_prompt=%s",
                    uid_log,
                    _log_safe_single_line(prompt_for_hash),
                )
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                max_completion_tokens=4096,
            )
            finish_reason = None
            try:
                finish_reason = response.choices[0].finish_reason
            except Exception:
                finish_reason = None
            self.logger.warning(
                "[PARTNER] partner_llm_fallback user_id=%s finish_reason=%s",
                uid_log,
                finish_reason,
            )
            if self._llm_debug_logs:
                raw_response = (
                    response.model_dump_json()
                    if hasattr(response, "model_dump_json")
                    else repr(response)
                )
                self.logger.warning(
                    "[PARTNER] partner_llm_fallback user_id=%s raw_api_response=%s",
                    uid_log,
                    _log_safe_single_line(raw_response),
                )
        except Exception as e:
            self._record_llm_stat("request_errors")
            self.logger.warning(
                "[PARTNER] partner_llm_fallback user_id=%s OpenAI request failed: %s",
                uid_log,
                e,
            )
            return _failure_outcome(prompt_for_hash, _synthesize_rationale())

        if getattr(response, "usage", None):
            self._last_token_usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }

        try:
            content = _extract_chat_message_content(response.choices[0].message)
        except (IndexError, AttributeError):
            content = ""

        if not content:
            self._record_llm_stat("empty_content")
            self.logger.warning(
                "[PARTNER] partner_llm_fallback user_id=%s empty model content company=%s; retrying without json mode",
                uid_log,
                scout_output.get("name", "Unknown"),
            )
            try:
                retry_response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    max_completion_tokens=4096,
                )
                retry_finish_reason = None
                try:
                    retry_finish_reason = retry_response.choices[0].finish_reason
                except Exception:
                    retry_finish_reason = None
                self.logger.warning(
                    "[PARTNER] partner_llm_fallback user_id=%s finish_reason_retry=%s",
                    uid_log,
                    retry_finish_reason,
                )
                if self._llm_debug_logs:
                    retry_raw = (
                        retry_response.model_dump_json()
                        if hasattr(retry_response, "model_dump_json")
                        else repr(retry_response)
                    )
                    self.logger.warning(
                        "[PARTNER] partner_llm_fallback user_id=%s raw_api_response_retry=%s",
                        uid_log,
                        _log_safe_single_line(retry_raw),
                    )
                try:
                    content = _extract_chat_message_content(retry_response.choices[0].message)
                except (IndexError, AttributeError):
                    content = ""
            except Exception as e:
                self._record_llm_stat("retry_request_errors")
                self.logger.warning(
                    "[PARTNER] partner_llm_fallback user_id=%s retry request failed: %s",
                    uid_log,
                    e,
                )
                content = ""
            if not content:
                try:
                    content = self._compact_llm_rescue_call(
                        uid_log=uid_log,
                        model=self.model,
                        scout_output=scout_output,
                        review_output=review_output,
                        trigger_reason=trigger_reason,
                    )
                except Exception as e:
                    self._record_llm_stat("rescue_request_errors")
                    self.logger.warning(
                        "[PARTNER] partner_llm_fallback user_id=%s compact rescue failed: %s",
                        uid_log,
                        e,
                    )
                    content = ""
            if not content:
                return _failure_outcome(prompt_for_hash, _synthesize_rationale())

        llm_result = _parse_llm_json_object(content)
        if not llm_result:
            self._record_llm_stat("malformed_json")
            self.logger.warning(
                "[PARTNER] partner_llm_fallback user_id=%s malformed JSON company=%s",
                uid_log,
                scout_output.get("name", "Unknown"),
            )
            return _failure_outcome(prompt_for_hash, _synthesize_rationale())

        raw_recommendation = llm_result.get("recommendation")
        recommendation = str(raw_recommendation).strip().upper() if raw_recommendation is not None else ""
        if recommendation not in ("INVEST", "PASS", "MONITOR"):
            self._record_llm_stat("invalid_decision")
            self.logger.warning(
                "[PARTNER] partner_llm_fallback user_id=%s invalid recommendation=%r company=%s",
                uid_log,
                raw_recommendation,
                scout_output.get("name", "Unknown"),
            )
            return _failure_outcome(prompt_for_hash, _synthesize_rationale())

        decision_rationale = (
            llm_result.get("decision_rationale")
            or llm_result.get("reasoning")
            or llm_result.get("rationale")
            or ""
        )
        decision_rationale = str(decision_rationale).strip()
        if not decision_rationale:
            decision_rationale = f"LLM edge-case decision: {trigger_reason}"

        conf_raw = llm_result.get("confidence")
        try:
            conf_float = max(0.0, min(1.0, float(conf_raw or 0.5)))
        except (TypeError, ValueError):
            conf_float = 0.5

        # Snapshot — use LLM output or fall back to scout data
        snap_raw = llm_result.get("snapshot")
        if isinstance(snap_raw, dict) and snap_raw.get("one_liner"):
            snapshot = snap_raw
        else:
            snapshot = {
                "one_liner": scout_output.get("one_line", ""),
                "stage": scout_output.get("funding_stage"),
                "key_signal": None,
            }

        risks_raw = llm_result.get("risks")
        llm_risks: List[str] = (
            [str(r) for r in risks_raw if isinstance(r, str)] if isinstance(risks_raw, list) else []
        ) or list(dict.fromkeys((review_output.get("key_risks") or []) + assumption_risks))[:5]

        next_act = self._normalize_next_action(
            str(llm_result.get("next_action") or "")
            or self._next_action_for_llm_decision(recommendation, next_actions)
        )
        human_rev = bool(llm_result.get("human_review_required", recommendation != "PASS"))

        result = {
            "recommendation": recommendation,
            "confidence": round(conf_float, 2),
            "decision": _recommendation_to_legacy_decision(recommendation),
            "conviction_level": _confidence_float_to_conviction_level(conf_float),
            "thesis": str(llm_result.get("thesis") or scout_output.get("primary_thesis") or scout_output.get("one_line") or "").strip(),
            "why_this_matters": str(llm_result.get("why_this_matters") or scout_output.get("why_now") or "").strip(),
            "snapshot": snapshot,
            "market_insight": str(llm_result.get("market_insight") or "").strip(),
            "product_edge": str(llm_result.get("product_edge") or "").strip(),
            "traction_signals": llm_result.get("traction_signals"),
            "risks": llm_risks[:5],
            "decision_rationale": decision_rationale,
            "rationale": decision_rationale,
            "next_action": next_act,
            "human_review_required": human_rev,
            "llm_fallback_reason": trigger_reason,
            "prompt_version": hash_prompt(prompt_for_hash),
        }
        self.logger.warning(
            "[PARTNER] partner_llm_fallback_metrics user_id=%s stats=%s",
            uid_log,
            json.dumps(self._llm_stats, sort_keys=True),
        )
        return result
