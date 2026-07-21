"""
Partner decision engine.
Rule-based, deterministic decision making.
Uses versioned partner rules from resources/config (via policy_resolver).
Default mode: NO LLM calls. LLM only for edge cases (contradictory scores, MEDIUM borderline, missing assumptions).
"""
import os
import json
import inspect
import copy
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from openai import OpenAI
from utils.openai_client import build_openai_client
from utils.prompt_version import hash_prompt
from utils.scoring import compute_overall_score
from utils.settings_loader import load_settings, recommendation_for_score_from_fund_config
from utils.partner_codes import legacy_from_recommendation, recommendation_from_legacy
from evaluation_v2.prerequisites import EvaluationPrerequisites
from evaluation_v2.governed_scoring import (
    configured_scoring_dimensions,
    validate_governed_scoring_trace,
)
from evaluation_v2.partner_rules import (
    LLMFallbackTriggers,
    NextActions,
    PartnerRules,
    boundary_comparisons,
    parse_partner_rules,
    partner_rules_document,
)

from partner.rationale import (
    compose_decision_rationale,
    derive_situation_tags,
    primary_tag,
)


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


def _log_safe_single_line(blob: str, max_len: int = 6000) -> str:
    """Collapse newlines so one log record stays on one physical line (TTY readline consumers)."""
    s = " ".join((blob or "").replace("\r\n", "\n").replace("\r", "\n").split())
    if len(s) > max_len:
        return s[: max_len - 24] + " ...[truncated]"
    return s


def _partner_rules_json_for_prompt(rules: PartnerRules) -> str:
    """Serialize partner rules; shrink if too large for the prompt token budget."""
    document = partner_rules_document(rules)
    raw = json.dumps(document, ensure_ascii=False, indent=2)
    if len(raw) <= _MAX_RULES_JSON_CHARS:
        return raw
    slim = {
        "version": document["version"],
        "description": document["description"],
        "score_thresholds": document["score_thresholds"],
        "verdict_rules": document["verdict_rules"],
        "llm_fallback_triggers": document["llm_fallback_triggers"],
        "contradictory_scores": document["contradictory_scores"],
        "next_actions": document["next_actions"],
        "quality_labels": document["quality_labels"],
    }
    raw2 = json.dumps(slim, ensure_ascii=False, indent=2)
    if len(raw2) <= _MAX_RULES_JSON_CHARS:
        return raw2 + "\n/* note: long keyword lists from full partner_rules were omitted */\n"
    return _json_within_budget(slim, _MAX_RULES_JSON_CHARS)


def _json_within_budget(obj: Any, max_chars: int) -> str:
    """Serialize obj to JSON that fits within max_chars and is ALWAYS valid JSON.

    Char-boundary truncation (``json.dumps(obj)[:n] + "...(truncated)"``) can emit
    malformed JSON into an LLM prompt — a brace/quote gets cut mid-structure and the
    model sees broken syntax. Instead we shrink the *structure* (dropping the largest
    keys / trailing list elements) and leave an explicit elision marker, so the
    emitted text always parses. Size is best-effort; validity is guaranteed.
    """
    raw = json.dumps(obj, ensure_ascii=False)
    if len(raw) <= max_chars:
        return raw
    if isinstance(obj, dict):
        kept = dict(obj)
        # Drop the largest-serialized values first until the marked dict fits.
        for key in sorted(
            obj.keys(),
            key=lambda k: len(json.dumps(obj[k], ensure_ascii=False)),
            reverse=True,
        ):
            marked = {**kept, "_elided_keys": True}
            if len(json.dumps(marked, ensure_ascii=False)) <= max_chars:
                return json.dumps(marked, ensure_ascii=False)
            kept.pop(key, None)
        return json.dumps({"_elided_keys": True}, ensure_ascii=False)
    if isinstance(obj, list):
        kept_list = list(obj)
        while kept_list:
            candidate = kept_list + [f"...(+{len(obj) - len(kept_list)} elided)"]
            cand_json = json.dumps(candidate, ensure_ascii=False)
            if len(cand_json) <= max_chars:
                return cand_json
            kept_list.pop()
        return json.dumps([f"...({len(obj)} items elided)"], ensure_ascii=False)
    # Scalars / unsupported: emit a valid JSON string rather than a sliced value.
    return json.dumps("[elided: exceeds prompt budget]", ensure_ascii=False)


def _merge_risks(
    primary: Optional[List[str]],
    secondary: Optional[List[str]],
    limit: int = 5,
) -> List[str]:
    """Combine two risk lists, preserving order, de-duplicating, capped at ``limit``."""
    combined = list(primary or []) + list(secondary or [])
    return list(dict.fromkeys(combined))[:limit]


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
        except Exception as e:
            logger.debug("parsed->json serialization failed; falling through: %s", e)
    refusal = getattr(message, "refusal", None)
    if isinstance(refusal, str) and refusal.strip():
        return refusal.strip()
    return ""


def _load_partner_rules() -> PartnerRules:
    """
    Load partner rules via policy_resolver (resources/config/active.json + versioned JSON).
    """
    from core.policy_resolver import get_partner_rules

    return parse_partner_rules(get_partner_rules())


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
        use_resource_fund_thesis_fallback: bool = True,
        evaluation_prerequisites: Optional[EvaluationPrerequisites] = None,
        include_deal_context_digest: Optional[bool] = None,
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
        self.evaluation_prerequisites = evaluation_prerequisites
        if evaluation_prerequisites is not None:
            evaluation_prerequisites.require_tenant(
                self.tenant_user_id, context="PartnerDecisionEngine"
            )
            use_resource_fund_thesis_fallback = False
        self.use_resource_fund_thesis_fallback = bool(use_resource_fund_thesis_fallback)
        self.llm_call_count = 0
        if evaluation_prerequisites is not None:
            self._rules = evaluation_prerequisites.partner_rules
            self._fund_config = copy.deepcopy(evaluation_prerequisites.fund_config)
            self.evaluation_policy = evaluation_prerequisites.policy.model_copy(
                deep=True
            )
        else:
            self._rules = _load_partner_rules()
            self._fund_config = {}
            self.evaluation_policy = None
        if self.tenant_user_id and evaluation_prerequisites is None:
            try:
                settings = load_settings(self.tenant_user_id)
                fc = settings.get("fund_config") if isinstance(settings.get("fund_config"), dict) else {}
                self._fund_config = dict(fc)
                if self._fund_config:
                    self.logger.info(
                        "partner_settings user_id=%s score_bands=%d thresholds=%s",
                        self.tenant_user_id[:24],
                        len(self._fund_config.get("scoreBands") or []),
                        self._fund_config.get("thresholds") or {},
                    )
            except Exception as e:
                self.logger.warning("Partner settings unavailable, using resource rules: %s", e)
        self.api_key = (api_key or os.getenv("OPENAI_API_KEY", "")).strip()
        self.model = model or os.getenv("PARTNER_MODEL", "gpt-5-nano")
        self.provider_id = "openai"
        self._include_deal_context_digest = (
            bool(include_deal_context_digest)
            if include_deal_context_digest is not None
            else os.getenv(
                "PARTNER_LLM_INCLUDE_DEAL_CONTEXT_DIGEST", ""
            ).strip().lower()
            in ("1", "true", "yes")
        )
        # This hashes the exact source that constructs both system and user
        # prompts. It is captured once, alongside the digest toggle, before any
        # evaluation can run.
        self.prompt_template_version = hash_prompt(
            inspect.getsource(type(self)._decide_with_llm)
        )
        if self.api_key:
            self.client = build_openai_client(self.api_key)
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

    def close(self) -> None:
        """Release the OpenAI client (httpx pool); rebuilt every pipeline cycle."""
        from utils.resource_cleanup import close_openai_client

        close_openai_client(getattr(self, "client", None))
        self.client = None

    def _verdict_label(self, verdict: str) -> str:
        """Human-readable quality label for verdict. Uses quality_labels from rules."""
        return self._rules.quality_labels.for_verdict(verdict)

    def _get_rules(self) -> PartnerRules:
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

    def _avg_score_and_dims(self, review_output: Dict[str, Any]) -> Tuple[float, int]:
        """Mean only genuinely scored core dimensions; retain coverage count."""
        values: List[float] = []
        structured = review_output.get("structured_scoring")
        structured = structured if isinstance(structured, dict) else None
        prerequisites = self.evaluation_prerequisites
        dimensions = (
            configured_scoring_dimensions(prerequisites)
            if prerequisites is not None
            else ("market", "product", "technical", "execution")
        )
        for dimension in dimensions:
            if structured is not None:
                detail = structured.get(dimension)
                if not isinstance(detail, dict) or bool(detail.get("unscored")):
                    continue
            raw = (
                structured[dimension].get("score")
                if structured is not None
                else review_output.get(f"{dimension}_score")
            )
            try:
                if raw is not None:
                    values.append(float(raw))
            except (TypeError, ValueError):
                continue
        if not values:
            return 0.0, 0
        if prerequisites is not None and len(values) == len(dimensions):
            overall = structured.get("overall_score") if structured is not None else None
            if isinstance(overall, (int, float)) and not isinstance(overall, bool):
                return float(overall), len(values)
        return sum(values) / len(values), len(values)

    def _canonical_recommendation(self, avg_score: float) -> str:
        if self.evaluation_policy is not None:
            advance_threshold = self.evaluation_policy.advance_threshold
            pass_threshold = self.evaluation_policy.pass_threshold
        elif self._fund_config.get("scoreBands"):
            return recommendation_for_score_from_fund_config(avg_score, self._fund_config)
        else:
            thresholds = self._rules.score_thresholds
            advance_comparison, pass_comparison = boundary_comparisons(self._rules)
            if (
                advance_comparison != "greater_than_or_equal"
                or pass_comparison != "less_than"
            ):
                raise ValueError("partner_rules has unsupported boundary semantics")
            advance_threshold = float(thresholds.min_avg_strong_yes)
            pass_threshold = float(thresholds.min_avg_pass)
        if avg_score >= advance_threshold:
            return "INVEST"
        if avg_score < pass_threshold:
            return "PASS"
        return "MONITOR"

    def _apply_final_recommendation_fields(
        self,
        result: Dict[str, Any],
        final_recommendation: str,
        assumption_risks: Optional[List[str]] = None,
        *,
        next_action: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Attach canonical headline + legacy decision + policy next_action (normalized)."""
        na = self._get_rules().next_actions
        raw_next = (
            next_action
            if next_action is not None
            else self._next_action_for_llm_decision(final_recommendation, na)
        )
        result["recommendation"] = final_recommendation
        result["decision"] = legacy_from_recommendation(final_recommendation)
        result["assumption_risks"] = list(assumption_risks or [])
        result["next_action"] = self._normalize_next_action(raw_next)
        return result

    @staticmethod
    def _handoff_quality_from_review(review_output: Dict[str, Any]) -> Dict[str, Any]:
        raw = review_output.get("handoff_quality")
        return raw if isinstance(raw, dict) else {}

    def _apply_handoff_quality_fields(
        self,
        result: Dict[str, Any],
        handoff_quality: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Escalate serious handoff quality issues without changing recommendation."""
        if not isinstance(handoff_quality, dict) or not handoff_quality:
            return result
        flags = [
            str(x).strip()
            for x in (handoff_quality.get("quality_flags") or [])
            if str(x).strip()
        ]
        serious = {
            "weak_sources",
            "missing_evidence",
            "contested_review",
            "low_signal_confidence",
            "thesis_mismatch",
        }
        if bool(handoff_quality.get("human_review_recommended")) or any(f in serious for f in flags):
            result["human_review_required"] = True
        if flags:
            existing = [
                str(x).strip()
                for x in (result.get("decision_drivers") or [])
                if str(x).strip()
            ]
            result["decision_drivers"] = list(dict.fromkeys(existing + flags))
        missing = [
            str(x).strip()
            for x in (handoff_quality.get("missing_evidence") or [])
            if str(x).strip()
        ]
        if missing:
            risks = [
                str(x).strip()
                for x in (result.get("risks") or [])
                if str(x).strip()
            ]
            risk_lines = [f"Missing evidence: {m}" for m in missing]
            result["risks"] = list(dict.fromkeys(risks + risk_lines))[:5]
        return result

    def _enforce_canonical_recommendation(
        self,
        result: Dict[str, Any],
        avg_score: float,
        assumption_risks: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Backward-compatible alias: canonical recommendation from average score."""
        forced = self._canonical_recommendation(avg_score)
        return self._apply_final_recommendation_fields(result, forced, assumption_risks)

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
        return tas >= float(self._get_rules().mandate_fit.strong_fit_min)

    @staticmethod
    def _is_medium_borderline_edge_case(
        avg_score: float,
        min_avg_borderline_low: float,
        max_avg_borderline_high: float,
        llm_triggers: LLMFallbackTriggers,
    ) -> bool:
        """
        Trigger MEDIUM borderline LLM fallback only near the configured cutoff.
        """
        if not (min_avg_borderline_low <= avg_score < max_avg_borderline_high):
            return False
        edge_window = float(llm_triggers.medium_borderline_edge_window)
        return avg_score >= (max_avg_borderline_high - edge_window)

    @staticmethod
    def _is_low_score_near_threshold_edge_case(
        avg_score: float,
        min_avg_pass: float,
        llm_triggers: LLMFallbackTriggers,
    ) -> bool:
        """
        Allow LLM fallback for MEDIUM decisions that are just below pass threshold.
        The policy window is measured below min_avg_pass.
        """
        if avg_score >= min_avg_pass:
            return False
        near_window = float(llm_triggers.low_score_near_threshold_window)
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

    def _finalize_thesis_and_mandate_gate(
        self,
        result: Dict[str, Any],
        review_output: Dict[str, Any],
        scout_output: Dict[str, Any],
        avg_score: float,
        avg_dims: int,
    ) -> Dict[str, Any]:
        """
        Separate the two judgments a fund actually cares about and gate on the second:
          - company_quality: conviction-bearing average score (0-10).
          - fund_fit: thesis alignment (0-10) + label + confidence.

        A strong company that is off-thesis is NOT auto-recommended INVEST — it is HELD
        (mandate_override_required) for an explicit IC exception. Thresholds live in the
        versioned `mandate_fit` block of partner_rules, never hardcoded here.
        """
        mf = self._get_rules().mandate_fit
        tas = self._optional_thesis_alignment_score(review_output)  # 0-1 or None

        result["company_quality"] = round(float(avg_score), 2)

        if tas is None:
            # Thesis-blind (no active mandate / alignment not computed): nothing to gate.
            result["fund_fit"] = None
            result["fund_fit_label"] = None
            result["fund_fit_confidence"] = None
            result["mandate_gate"] = "no_mandate"
            result["mandate_override_required"] = False
            self._log_finalize(scout_output, avg_score, avg_dims, "no_mandate", result)
            return result

        strong_min = float(mf.strong_fit_min)
        partial_min = float(mf.partial_fit_min)
        weak_min = float(mf.weak_fit_min)
        gate_below = float(mf.gate_invest_below)
        low_conf_max = float(mf.low_confidence_max)
        enabled = mf.enabled

        conf_raw = review_output.get("thesis_alignment_confidence")
        try:
            conf = float(conf_raw) if conf_raw is not None else None
        except (TypeError, ValueError):
            conf = None

        if tas >= strong_min:
            label = "Strong fit"
        elif tas >= partial_min:
            label = "Partial fit"
        elif tas >= weak_min:
            label = "Weak fit"
        else:
            label = "Outside thesis"

        result["fund_fit"] = round(tas * 10.0, 2)
        result["fund_fit_label"] = label
        result["fund_fit_confidence"] = conf

        # An explicit IC exception lets a strong-but-off-thesis company proceed.
        override = bool(
            review_output.get("mandate_exception")
            or scout_output.get("mandate_exception")
            or result.get("mandate_override")
        )

        gate = "clear"
        override_required = False

        def _append_note(note: str) -> None:
            r = (result.get("decision_rationale") or "").rstrip()
            if note not in r:
                merged = (r + " " + note).strip()
                result["decision_rationale"] = merged
                result["rationale"] = merged

        if enabled and result.get("recommendation") == "INVEST" and tas < gate_below and not override:
            held = mf.held_recommendation
            result = self._apply_final_recommendation_fields(
                result, held, result.get("assumption_risks")
            )
            result["next_action"] = self._normalize_next_action(
                mf.held_next_action
            )
            result["human_review_required"] = True
            override_required = True
            gate = "held"
            _append_note("Held for mandate exception: strong company, outside this fund's thesis.")
        elif tas < weak_min:
            gate = "outside_thesis"
            _append_note("Clear thesis mismatch.")
        elif tas < partial_min:
            gate = "weak_fit"
            _append_note("Low thesis alignment.")

        if conf is not None and conf < low_conf_max:
            result["human_review_required"] = True

        result["mandate_gate"] = gate
        result["mandate_override_required"] = override_required
        self._log_finalize(scout_output, avg_score, avg_dims, gate, result)
        return result

    def _log_finalize(
        self,
        scout_output: Dict[str, Any],
        avg_score: float,
        avg_dims: int,
        gate: str,
        result: Dict[str, Any],
    ) -> None:
        self.logger.info(
            "partner_decide company=%s avg_score=%.2f avg_dims=%d mandate_gate=%s fund_fit=%s final=%s",
            scout_output.get("name", ""),
            avg_score,
            avg_dims,
            gate,
            result.get("fund_fit"),
            result.get("recommendation"),
        )

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
        if self.evaluation_prerequisites is not None:
            validate_governed_scoring_trace(
                review_output.get("structured_scoring"),
                self.evaluation_prerequisites,
                require_resolved=True,
            )
        rules = self._get_rules()
        verdict_rules = rules.verdict_rules
        score_thresholds = rules.score_thresholds
        next_actions = rules.next_actions

        portfolio_context = self._get_portfolio_context() if self.portfolio_store else {}
        thesis_block = ""
        if fund_thesis:
            pj = fund_thesis.get("parsed_json") or {}
            thesis_block = (
                "\nFUND THESIS MANDATE:\n"
                f"version_id: {fund_thesis.get('version_id', '')}\n"
                f"{json.dumps(pj, ensure_ascii=False)[:8000]}\n"
            )
        if self.use_resource_fund_thesis_fallback:
            try:
                from core.fund_thesis_resolver import format_fund_thesis_context_for_prompt

                resource_ctx = "" if fund_thesis else format_fund_thesis_context_for_prompt()
                if resource_ctx:
                    thesis_block = (thesis_block or "") + resource_ctx
            except Exception as e:
                logger.debug("Resource fund-thesis context unavailable: %s", e)

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
        llm_triggers_global = rules.llm_fallback_triggers
        grey_zone_score = review_output.get("confidence_adjusted_score")
        if grey_zone_score is None:
            grey_zone_score = avg_score
        grey_zone_min = float(score_thresholds.grey_zone_min)
        grey_zone_max = float(score_thresholds.grey_zone_max)
        grey_zone_active = (
            llm_triggers_global.grey_zone_deep_dive
            and grey_zone_min <= grey_zone_score <= grey_zone_max
        )

        min_avg_pass = float(score_thresholds.min_avg_pass)
        min_avg_strong_yes = float(score_thresholds.min_avg_strong_yes)
        min_avg_medium_maybe = float(score_thresholds.min_avg_medium_maybe)
        min_avg_borderline_low = float(score_thresholds.min_avg_borderline_low)
        max_avg_borderline_high = float(score_thresholds.max_avg_borderline_high)
        fc_thresholds = self._fund_config.get("thresholds") if isinstance(self._fund_config.get("thresholds"), dict) else {}
        if fc_thresholds:
            try:
                min_avg_pass = float(fc_thresholds.get("partnerReview", min_avg_pass * 10)) / 10.0
                min_avg_strong_yes = float(fc_thresholds.get("escalation", min_avg_strong_yes * 10)) / 10.0
                min_avg_medium_maybe = float(fc_thresholds.get("monitor", min_avg_medium_maybe * 10)) / 10.0
                min_avg_borderline_low = float(fc_thresholds.get("autoPass", min_avg_borderline_low * 10)) / 10.0
                # Preserve the ordering invariant the rule ladder depends on:
                # autoPass <= partnerReview <= monitor <= escalation. A fund_config
                # with monitor > escalation (no backend model validator forbids it)
                # would otherwise push min_avg_medium_maybe above min_avg_strong_yes,
                # making the MEDIUM-escalation rule unreachable and silently dropping
                # high-avg contested deals to the no-human-review default branch.
                min_avg_medium_maybe = min(min_avg_medium_maybe, min_avg_strong_yes)
                min_avg_borderline_low = min(min_avg_borderline_low, min_avg_pass)
            except (TypeError, ValueError):
                pass

        assumption_risks = self._compute_assumption_risks(
            scout_output, review_output, assumption_feedback
        )
        conviction_adjust = -1 if assumption_risks else 0

        # Narrative fields computed once from inputs — reused by all rule branches
        n_thesis, n_why, n_snapshot, n_market, n_product, n_traction = (
            self._build_narrative_from_inputs(scout_output, review_output)
        )
        # Merged risks: key_risks + assumption_risks, deduplicated, max 5
        merged_risks: List[str] = _merge_risks(key_risks, assumption_risks)
        has_critical_risk = self._has_critical_risk(key_risks, rules)

        required_dimensions = (
            configured_scoring_dimensions(self.evaluation_prerequisites)
            if self.evaluation_prerequisites is not None
            else ("market", "product", "technical", "execution")
        )
        if avg_dims < len(required_dimensions):
            missing_dimensions = [
                dimension
                for dimension in required_dimensions
                if (
                    not isinstance(review_output.get("structured_scoring"), dict)
                    or not isinstance(
                        review_output["structured_scoring"].get(dimension), dict
                    )
                    or review_output["structured_scoring"][dimension].get("unscored")
                    or review_output["structured_scoring"][dimension].get("score")
                    is None
                )
            ]
            evidence_risk = (
                "Insufficient evidence coverage for required dimensions: "
                + ", ".join(missing_dimensions)
            )
            if has_critical_risk:
                result = self._create_decision(
                    recommendation="PASS",
                    conviction=8,
                    decision_rationale=(
                        "Critical diligence risk: the identified blocker requires "
                        "a pass even though evaluation coverage is incomplete."
                    ),
                    next_action=next_actions.critical_risks,
                    human_review_required=True,
                    thesis=n_thesis,
                    why_this_matters=n_why,
                    snapshot=n_snapshot,
                    market_insight=n_market,
                    product_edge=n_product,
                    traction_signals=n_traction,
                    risks=_merge_risks(merged_risks, [evidence_risk]),
                )
                result["decision_drivers"] = [
                    "critical_risk",
                    "insufficient_evidence_coverage",
                ]
                result = self._apply_final_recommendation_fields(
                    result,
                    "PASS",
                    assumption_risks,
                    next_action=next_actions.critical_risks,
                )
                result["human_review_required"] = True
                return self._finalize_thesis_and_mandate_gate(
                    result, review_output, scout_output, avg_score, avg_dims
                )
            result = self._create_decision(
                recommendation="MONITOR",
                conviction=3,
                decision_rationale=(
                    "Insufficient evidence: required evaluation dimensions are "
                    "unscored, so the available evidence cannot support an "
                    "investment or pass recommendation."
                ),
                next_action=next_actions.human_review_monitor,
                human_review_required=True,
                thesis=n_thesis,
                why_this_matters=n_why,
                snapshot=n_snapshot,
                market_insight=n_market,
                product_edge=n_product,
                traction_signals=n_traction,
                risks=_merge_risks(merged_risks, [evidence_risk]),
            )
            result["decision_drivers"] = ["insufficient_evidence_coverage"]
            result = self._apply_final_recommendation_fields(
                result,
                "MONITOR",
                assumption_risks,
                next_action=next_actions.human_review_monitor,
            )
            result["risks"] = _merge_risks(merged_risks, [evidence_risk])
            result["human_review_required"] = True
            return self._finalize_thesis_and_mandate_gate(
                result, review_output, scout_output, avg_score, avg_dims
            )

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
        if not has_missing_team and self._has_strong_qualitative(
            review_output.get("team_analysis") or [], rules
        ):
            conviction_adjust += 1
        if not has_missing_business_model and self._has_strong_qualitative(
            review_output.get("business_model_analysis") or [], rules
        ):
            conviction_adjust += 1

        has_red_flags = self._has_red_flags(key_risks, rules)
        has_contradiction = self._has_contradictory_scores(
            market_score, product_score, technical_score, execution_score, rules
        )
        has_missing_assumptions = self._has_missing_assumptions_affecting_decision(
            assumption_feedback, assumption_risks, rules
        )
        has_missing_critical_qualitative = has_missing_team or has_missing_business_model

        startup_sector = scout_output.get("sector", "")
        startup_funding_stage = scout_output.get("funding_stage")
        if portfolio_context:
            sector_counts = portfolio_context.get("sector_counts", {})
            total = portfolio_context.get("total_portfolio_size", 0)
            if sector_counts.get(startup_sector, 0) >= 3:
                conviction_adjust -= 2
            if total > 20 and startup_funding_stage == "Pre-Seed":
                conviction_adjust -= 1

        score_recommendation = self._canonical_recommendation(avg_score)
        if has_critical_risk:
            score_recommendation = "PASS"
        reviewer_disagreement = bool(review_output.get("reviewer_disagreement", False))
        handoff_quality = self._handoff_quality_from_review(review_output)

        tags = derive_situation_tags(
            effective_verdict=effective_verdict,
            avg_score=avg_score,
            min_avg_pass=min_avg_pass,
            min_avg_strong_yes=min_avg_strong_yes,
            min_avg_medium_maybe=min_avg_medium_maybe,
            min_avg_borderline_low=min_avg_borderline_low,
            max_avg_borderline_high=max_avg_borderline_high,
            has_critical_risk=has_critical_risk,
            has_contradiction=has_contradiction,
            grey_zone_active=grey_zone_active,
            reviewer_disagreement=reviewer_disagreement,
            has_missing_critical_qualitative=has_missing_critical_qualitative,
        )
        primary = primary_tag(tags)
        label = self._verdict_label(effective_verdict)
        sector_conc = bool(
            portfolio_context and portfolio_context.get("sector_counts", {}).get(startup_sector, 0) >= 3
        )

        weak_rule = verdict_rules.weak
        strong_rule = verdict_rules.strong
        medium_rule = verdict_rules.medium

        def _aligned_rationale(
            recommendation: str,
        ) -> Tuple[str, List[str]]:
            return compose_decision_rationale(
                final_recommendation=recommendation,
                tags=tags,
                primary=primary,
                label=label,
                avg_score=avg_score,
                market_score=int(market_score),
                product_score=int(product_score),
                technical_score=int(technical_score),
                execution_score=int(execution_score),
                min_avg_pass=min_avg_pass,
                min_avg_strong_yes=min_avg_strong_yes,
                min_avg_medium_maybe=min_avg_medium_maybe,
                min_avg_borderline_low=min_avg_borderline_low,
                max_avg_borderline_high=max_avg_borderline_high,
                has_contradiction=has_contradiction,
                reviewer_disagreement=reviewer_disagreement,
                sector_concentration_note=sector_conc,
            )

        def _default_deterministic_action(
            recommendation: str,
            human_review_required: bool,
        ) -> str:
            if recommendation == "INVEST":
                return (
                    next_actions.request_cap_table_and_review
                    if human_review_required
                    else next_actions.request_cap_table
                )
            if recommendation == "PASS":
                return next_actions.default_no
            return (
                next_actions.human_review_monitor
                if human_review_required
                else next_actions.monitor
            )

        def _emit_deterministic(
            recommendation: str,
            conviction: int,
            human_rev: bool,
            *,
            next_action: Optional[str] = None,
        ) -> Dict[str, Any]:
            effective_human_review = bool(human_rev or has_red_flags)
            effective_next_action = (
                next_action
                if next_action is not None
                else _default_deterministic_action(
                    recommendation, effective_human_review
                )
            )
            rationale, drivers = _aligned_rationale(recommendation)
            result = self._create_decision(
                recommendation=recommendation,
                conviction=conviction,
                decision_rationale=rationale,
                next_action=effective_next_action,
                human_review_required=effective_human_review,
                thesis=n_thesis,
                why_this_matters=n_why,
                snapshot=n_snapshot,
                market_insight=n_market,
                product_edge=n_product,
                traction_signals=n_traction,
                risks=merged_risks,
            )
            result["decision_drivers"] = drivers
            result = self._apply_final_recommendation_fields(
                result,
                recommendation,
                assumption_risks,
                next_action=effective_next_action,
            )
            result = self._apply_handoff_quality_fields(result, handoff_quality)
            return self._finalize_thesis_and_mandate_gate(
                result, review_output, scout_output, avg_score, avg_dims
            )

        # Rule 1: Critical diligence risks
        if has_critical_risk:
            return _emit_deterministic(
                "PASS",
                8 + conviction_adjust,
                True,
                next_action=next_actions.critical_risks,
            )

        # Rule 2: WEAK verdict (portfolio-aware conviction like other branches)
        if effective_verdict == "WEAK":
            return _emit_deterministic(
                recommendation_from_legacy(weak_rule.decision),
                weak_rule.conviction_level + conviction_adjust,
                weak_rule.human_review_required,
                next_action=weak_rule.next_action,
            )

        # Rule 3: Low average score → optional LLM edge case
        if avg_score < min_avg_pass:
            llm_triggers = rules.llm_fallback_triggers
            low_score_edge_case = (
                effective_verdict == "MEDIUM"
                and llm_triggers.low_score_near_threshold
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
                    final_recommendation=score_recommendation,
                    fund_thesis=fund_thesis,
                )
                return self._align_llm_partner_payload(
                    result,
                    final_recommendation=score_recommendation,
                    assumption_risks=assumption_risks,
                    tags=tags,
                    primary=primary,
                    label=label,
                    avg_score=avg_score,
                    market_score=int(market_score),
                    product_score=int(product_score),
                    technical_score=int(technical_score),
                    execution_score=int(execution_score),
                    min_avg_pass=min_avg_pass,
                    min_avg_strong_yes=min_avg_strong_yes,
                    min_avg_medium_maybe=min_avg_medium_maybe,
                    min_avg_borderline_low=min_avg_borderline_low,
                    max_avg_borderline_high=max_avg_borderline_high,
                    has_contradiction=has_contradiction,
                    reviewer_disagreement=reviewer_disagreement,
                    sector_concentration_note=sector_conc,
                    review_output=review_output,
                    scout_output=scout_output,
                    avg_dims=avg_dims,
                    force_human_review=has_red_flags,
                )

            return _emit_deterministic(
                score_recommendation,
                7 + conviction_adjust,
                False,
                next_action=next_actions.low_scores,
            )

        # Rule 4: STRONG verdict, pass bar met but below YES bar
        if effective_verdict == "STRONG" and min_avg_pass <= avg_score < min_avg_strong_yes:
            return _emit_deterministic(
                recommendation_from_legacy(
                    strong_rule.decision_below_strong_yes_bar
                ),
                strong_rule.conviction_level_below_strong_yes_bar + conviction_adjust,
                strong_rule.human_review_required_below_strong_yes_bar,
                next_action=strong_rule.next_action_below_strong_yes_bar,
            )

        # Rule 5: STRONG verdict + high score
        if effective_verdict == "STRONG" and avg_score >= min_avg_strong_yes:
            human_review = strong_rule.human_review_required_yes or has_missing_critical_qualitative
            return _emit_deterministic(
                recommendation_from_legacy(strong_rule.decision_yes),
                strong_rule.conviction_level_yes + conviction_adjust,
                human_review,
            )

        # Rule 6: MEDIUM verdict + strong average → optional LLM escalation
        if effective_verdict == "MEDIUM" and avg_score >= min_avg_medium_maybe:
            branch_recommendation = recommendation_from_legacy(
                medium_rule.decision_maybe
            )
            llm_triggers = rules.llm_fallback_triggers
            trigger_reason = ""
            if grey_zone_active:
                trigger_reason = (
                    f"Grey zone deep dive: S_adj={grey_zone_score:.2f} in "
                    f"[{grey_zone_min}, {grey_zone_max}]"
                )
            elif has_contradiction and llm_triggers.contradictory_scores:
                trigger_reason = "Contradictory scores detected (gap >= threshold)"
            elif has_missing_assumptions and llm_triggers.missing_assumptions_affecting_decision:
                trigger_reason = "Missing assumptions affecting decision"
            elif has_missing_critical_qualitative and llm_triggers.missing_critical_qualitative:
                trigger_reason = "Missing critical qualitative data (team/business model)"
            elif reviewer_disagreement and llm_triggers.reviewer_disagreement:
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
                    final_recommendation=branch_recommendation,
                    fund_thesis=fund_thesis,
                )
                return self._align_llm_partner_payload(
                    result,
                    final_recommendation=branch_recommendation,
                    assumption_risks=assumption_risks,
                    tags=tags,
                    primary=primary,
                    label=label,
                    avg_score=avg_score,
                    market_score=int(market_score),
                    product_score=int(product_score),
                    technical_score=int(technical_score),
                    execution_score=int(execution_score),
                    min_avg_pass=min_avg_pass,
                    min_avg_strong_yes=min_avg_strong_yes,
                    min_avg_medium_maybe=min_avg_medium_maybe,
                    min_avg_borderline_low=min_avg_borderline_low,
                    max_avg_borderline_high=max_avg_borderline_high,
                    has_contradiction=has_contradiction,
                    reviewer_disagreement=reviewer_disagreement,
                    sector_concentration_note=sector_conc,
                    review_output=review_output,
                    scout_output=scout_output,
                    avg_dims=avg_dims,
                    force_human_review=has_red_flags,
                )

            return _emit_deterministic(
                branch_recommendation,
                medium_rule.conviction_level_maybe + conviction_adjust,
                False,
            )

        # Rule 7: MEDIUM borderline band
        if effective_verdict == "MEDIUM" and min_avg_borderline_low <= avg_score < max_avg_borderline_high:
            branch_recommendation = recommendation_from_legacy(
                medium_rule.decision_borderline_no_llm
            )
            llm_triggers = rules.llm_fallback_triggers
            is_edge_case = self._is_medium_borderline_edge_case(
                avg_score=avg_score,
                min_avg_borderline_low=min_avg_borderline_low,
                max_avg_borderline_high=max_avg_borderline_high,
                llm_triggers=llm_triggers,
            )
            use_llm = (
                self.use_llm_fallback
                and (llm_triggers.medium_borderline_avg and is_edge_case or grey_zone_active)
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
                    final_recommendation=branch_recommendation,
                    fund_thesis=fund_thesis,
                )
                return self._align_llm_partner_payload(
                    result,
                    final_recommendation=branch_recommendation,
                    assumption_risks=assumption_risks,
                    tags=tags,
                    primary=primary,
                    label=label,
                    avg_score=avg_score,
                    market_score=int(market_score),
                    product_score=int(product_score),
                    technical_score=int(technical_score),
                    execution_score=int(execution_score),
                    min_avg_pass=min_avg_pass,
                    min_avg_strong_yes=min_avg_strong_yes,
                    min_avg_medium_maybe=min_avg_medium_maybe,
                    min_avg_borderline_low=min_avg_borderline_low,
                    max_avg_borderline_high=max_avg_borderline_high,
                    has_contradiction=has_contradiction,
                    reviewer_disagreement=reviewer_disagreement,
                    sector_concentration_note=sector_conc,
                    review_output=review_output,
                    scout_output=scout_output,
                    avg_dims=avg_dims,
                    force_human_review=has_red_flags,
                )

            return _emit_deterministic(
                branch_recommendation,
                medium_rule.conviction_level_borderline + conviction_adjust,
                False,
                next_action=medium_rule.next_action_borderline,
            )

        # Default path
        return _emit_deterministic(
            score_recommendation,
            6 + conviction_adjust,
            False,
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
        keywords = rules.assumption_risk_keywords
        feedback_lower = [f.lower() for f in assumption_feedback]
        for i, fb in enumerate(assumption_feedback):
            if any(kw in feedback_lower[i] for kw in keywords):
                risks.append(fb)
        biggest_unknown = scout_output.get("biggest_unknown") or ""
        if biggest_unknown.strip() and not any(biggest_unknown.strip() in r for r in risks):
            risks.append(f"Biggest unknown: {biggest_unknown.strip()}")
        return risks[:10]

    def _has_critical_risk(self, key_risks: List[str], rules: PartnerRules) -> bool:
        """Check if any risk indicates regulatory or execution impossibility (from rules)."""
        keywords = [keyword.lower() for keyword in rules.critical_risk_keywords]
        risks_lower = [r.lower() for r in key_risks]
        for risk in risks_lower:
            for keyword in keywords:
                if keyword in risk:
                    return True
        return False

    def _has_red_flags(self, key_risks: List[str], rules: PartnerRules) -> bool:
        """Check for missing-data or red-flag phrasing (from rules)."""
        keywords = [keyword.lower() for keyword in rules.red_flag_keywords]
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
        rules: PartnerRules,
    ) -> bool:
        """Detect contradictory scores using thresholds from rules."""
        cfg = rules.contradictory_scores
        min_gap = cfg.min_gap
        high_threshold = cfg.high_threshold
        low_threshold = cfg.low_threshold
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
        rules: PartnerRules,
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

        keywords = rules.assumption_risk_keywords
        feedback_lower = [f.lower() for f in assumption_feedback]
        for i, fb in enumerate(assumption_feedback):
            if any(kw in feedback_lower[i] for kw in keywords):
                return True
        return False

    def _has_missing_team(self, review_output: Dict[str, Any], rules: PartnerRules) -> bool:
        """True if team_analysis is absent or only [MISSING] placeholders."""
        team = review_output.get("team_analysis") or []
        if not team:
            return True
        missing_keywords = [keyword.lower() for keyword in rules.missing_qualitative_keywords]
        combined = " ".join(t.lower() for t in team)
        return any(kw in combined for kw in missing_keywords) and len(team) <= 2

    def _has_missing_business_model(self, review_output: Dict[str, Any], rules: PartnerRules) -> bool:
        """True if business_model_analysis is absent or only [MISSING] placeholders."""
        bm = review_output.get("business_model_analysis") or []
        if not bm:
            return True
        missing_keywords = [keyword.lower() for keyword in rules.missing_qualitative_keywords]
        combined = " ".join(t.lower() for t in bm)
        return any(kw in combined for kw in missing_keywords) and len(bm) <= 2

    def _has_strong_qualitative(
        self,
        items: List[str],
        rules: PartnerRules,
    ) -> bool:
        """True for substantive content not marked by configured missing keywords."""
        if not items or len(items) < 2:
            return False
        missing_keywords = [
            keyword.lower() for keyword in rules.missing_qualitative_keywords
        ]
        substantive = [
            item
            for item in items
            if not any(keyword in item.lower() for keyword in missing_keywords)
            and len(item.strip()) > 20
        ]
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
            recommendation = recommendation_from_legacy(
                legacy_decision, default_if_unknown="MONITOR"
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
            "decision": legacy_from_recommendation(recommendation),
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

    def _next_action_for_llm_decision(
        self, recommendation: str, next_actions: NextActions
    ) -> str:
        if recommendation == "INVEST":
            return next_actions.request_cap_table
        if recommendation == "PASS":
            return next_actions.default_no
        return next_actions.human_review_monitor

    def _compact_llm_rescue_call(
        self,
        uid_log: str,
        model: str,
        scout_output: Dict[str, Any],
        review_output: Dict[str, Any],
        trigger_reason: str,
        final_recommendation: str,
    ) -> str:
        """
        Final fallback call with a tiny prompt to avoid large-context/formatting failures.
        Returns raw model text content (possibly empty).
        """
        compact_prompt = (
            "Return ONLY a JSON object with keys: confidence, decision_rationale.\n"
            "confidence must be a float in [0,1].\n"
            "decision_rationale must be a non-empty string defending CANONICAL_DECISION.\n\n"
            f"CANONICAL_DECISION={final_recommendation}\n"
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

    def _align_llm_partner_payload(
        self,
        result: Dict[str, Any],
        *,
        final_recommendation: str,
        assumption_risks: List[str],
        tags,
        primary: str,
        label: str,
        avg_score: float,
        market_score: int,
        product_score: int,
        technical_score: int,
        execution_score: int,
        min_avg_pass: float,
        min_avg_strong_yes: float,
        min_avg_medium_maybe: float,
        min_avg_borderline_low: float,
        max_avg_borderline_high: float,
        has_contradiction: bool,
        reviewer_disagreement: bool,
        sector_concentration_note: bool,
        review_output: Dict[str, Any],
        scout_output: Dict[str, Any],
        avg_dims: int,
        force_human_review: bool = False,
    ) -> Dict[str, Any]:
        """Force rationale + headline to match canonical recommendation (LLM narrative only)."""
        rationale, drivers = compose_decision_rationale(
            final_recommendation=final_recommendation,
            tags=tags,
            primary=primary,
            label=label,
            avg_score=avg_score,
            market_score=market_score,
            product_score=product_score,
            technical_score=technical_score,
            execution_score=execution_score,
            min_avg_pass=min_avg_pass,
            min_avg_strong_yes=min_avg_strong_yes,
            min_avg_medium_maybe=min_avg_medium_maybe,
            min_avg_borderline_low=min_avg_borderline_low,
            max_avg_borderline_high=max_avg_borderline_high,
            has_contradiction=has_contradiction,
            reviewer_disagreement=reviewer_disagreement,
            sector_concentration_note=sector_concentration_note,
        )
        result["decision_rationale"] = rationale
        result["rationale"] = rationale
        result["decision_drivers"] = drivers
        result = self._apply_final_recommendation_fields(
            result, final_recommendation, assumption_risks
        )
        result = self._apply_handoff_quality_fields(
            result,
            self._handoff_quality_from_review(review_output),
        )
        if force_human_review:
            result["human_review_required"] = True
        return self._finalize_thesis_and_mandate_gate(
            result, review_output, scout_output, avg_score, avg_dims
        )

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
        final_recommendation: str = "MONITOR",
        fund_thesis: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        LLM path when rule engine defers (edge cases). Uses OpenAI chat.completions with JSON output.
        Canonical recommendation is fixed by the caller; model supplies defense narrative only.
        On missing client, empty/invalid response, or errors: safe fallback payload for alignment layer.
        """
        del context_memo  # omitted from prompt to respect token budget; rule path unchanged
        del portfolio_context
        del avg_dims  # caller uses for finalize + logging only

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
        next_actions = rules.next_actions
        verdict = review_output.get("verdict", "MEDIUM")
        score_reasoning = review_output.get("score_reasoning") or {}

        def _failure_outcome(prompt_snapshot: str, rationale: str) -> Dict[str, Any]:
            n_t, n_w, n_s, n_m, n_p, n_tr = self._build_narrative_from_inputs(
                scout_output, review_output
            )
            f_risks: List[str] = _merge_risks(review_output.get("key_risks"), assumption_risks)
            result = self._create_decision(
                recommendation=final_recommendation,
                conviction=1,
                decision_rationale=rationale,
                next_action=next_actions.human_review_contradictions,
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

        rules_json = _partner_rules_json_for_prompt(rules)
        tb = (thesis_block or "").strip()
        if len(tb) > _MAX_THESIS_MANDATE_CHARS:
            tb = tb[: _MAX_THESIS_MANDATE_CHARS - 30] + "\n...(truncated)\n"
        thesis_section = f"FUND THESIS MANDATE (and resource lens if present):\n{tb}\n\n" if tb else ""

        digest_prefix = ""
        if self._include_deal_context_digest:
            from utils.deal_context import build_deal_context_v1, format_deal_context_digest_prompt_line

            dc = build_deal_context_v1(scout_output, review_output, fund_thesis)
            digest_prefix = format_deal_context_digest_prompt_line(dc) + "\n\n"

        sr_json = _json_within_budget(score_reasoning, 3500)
        structured_scoring = review_output.get("structured_scoring") or {}
        policy_version_id = structured_scoring.get("policy_version_id") if isinstance(structured_scoring, dict) else None
        scoring_json = _json_within_budget(structured_scoring, 4500)

        ds = review_output.get("defensibility_score")
        ds_disp = ds if ds is not None else "N/A"

        est_raw = scout_output.get("est_tam")
        est_disp = str(est_raw).strip() if est_raw is not None and str(est_raw).strip() else "N/A"
        refs_raw = scout_output.get("references") or []
        refs_list = [r for r in refs_raw if isinstance(r, str) and r.strip()][:12]
        refs_json = _json_within_budget(refs_list, 2400)
        prov_raw = scout_output.get("field_provenance")
        prov_json = _json_within_budget(prov_raw if isinstance(prov_raw, dict) else {}, 800)

        user_prompt = f"""{digest_prefix}{thesis_section}STARTUP
display_name: {scout_output.get('name', 'Unknown')}
sector: {scout_output.get('sector', 'N/A')}
stage (funding): {scout_output.get('funding_stage', 'N/A')}
one_line: {scout_output.get('one_line', 'N/A')}
primary_thesis: {scout_output.get('primary_thesis', 'N/A')}
why_now: {scout_output.get('why_now', 'N/A')}
estimated_tam: {est_disp}
references (JSON array, may be elided): {refs_json}
field_provenance (JSON — source tags for enriched scout fields): {prov_json}

REVIEWER OUTPUT
verdict: {verdict}
market_score: {review_output.get('market_score', 0)}/10
product_score: {review_output.get('product_score', 0)}/10
technical_score: {review_output.get('technical_score', 0)}/10
execution_score: {review_output.get('execution_score', 0)}/10
defensibility_score: {ds_disp}/10
score_reasoning (full JSON): {sr_json}
policy_version_id: {policy_version_id or 'N/A'}
structured_scoring_with_policy_criteria (JSON, may be elided): {scoring_json}

THESIS ALIGNMENT (from review)
thesis_alignment_score: {review_output.get('thesis_alignment_score')}
thesis_matches_fund: {review_output.get('thesis_matches_fund')}
thesis_fit_points: {json.dumps(review_output.get('thesis_fit_points') or [], ensure_ascii=False)}
thesis_deviation_points: {json.dumps(review_output.get('thesis_deviation_points') or [], ensure_ascii=False)}

PARTNER_RULES_JSON (fund criteria; reason strictly against this policy)
{rules_json}

TRIGGER REASON (why the rule engine deferred)
{trigger_reason}

CANONICAL DECISION (fixed by fund score-band policy — must not be contradicted)
recommendation: {final_recommendation}

GROUNDING: For snapshot.key_signal, traction_signals, market_insight, and product_edge, only include non-null/non-empty text that paraphrases facts explicitly present in STARTUP or REVIEWER OUTPUT above. If nothing in those blocks supports a claim, use null or empty string for that field.

Return ONLY a single valid JSON object with exactly these keys (do NOT include "recommendation"):
{{
  "confidence": <float 0.0-1.0>,
  "thesis": "<investment thesis — 1 sentence>",
  "why_this_matters": "<market timing or structural shift — 1 sentence>",
  "snapshot": {{"one_liner": "<company one-liner>", "stage": "<funding stage or null>", "key_signal": "<top signal or null>"}},
  "market_insight": "<key market dynamic — 1 sentence>",
  "product_edge": "<meaningful differentiation or lack thereof — 1 sentence>",
  "traction_signals": "<traction evidence or null>",
  "risks": ["<risk 1>", "<risk 2>", "<risk 3>"],
  "decision_rationale": "<2-3 sentences defending the CANONICAL DECISION above using scores and thesis fit>",
  "next_action": "<specific next step for the team>",
  "human_review_required": <true|false>
}}
No markdown. No extra fields. Strictly under 350 words total information density. Be opinionated.
"""

        system_prompt = (
            "You are a Senior Investment Partner. Edge cases only: the deterministic rule path already passed. "
            "The CANONICAL DECISION is fixed by policy; your JSON must defend it, never overturn it. "
            "Apply PARTNER_RULES_JSON strictly. Output only valid JSON per the user instructions. "
            "Do not invent snapshot.key_signal, traction_signals, market_insight, or product_edge: "
            "each must restate information from the STARTUP and REVIEWER OUTPUT blocks in the user message, or be null/empty."
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
                        final_recommendation=final_recommendation,
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
        ) or _merge_risks(review_output.get("key_risks"), assumption_risks)

        next_act = self._normalize_next_action(
            str(llm_result.get("next_action") or "")
            or self._next_action_for_llm_decision(final_recommendation, next_actions)
        )
        human_rev = bool(llm_result.get("human_review_required", final_recommendation != "PASS"))

        result = {
            "recommendation": final_recommendation,
            "confidence": round(conf_float, 2),
            "decision": legacy_from_recommendation(final_recommendation),
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
