"""
Base Reviewer abstraction.
Reviewers evaluate Scout discoveries and emit structured assessments.
Uses /resources for scoring thresholds, red flag definitions, and evaluation guidance.
"""
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
import json
import os
import logging
import asyncio
import re
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from openai import OpenAI

from reviewer.schema import ReviewerOutput, validate_reviewer_output
from utils.prompt_version import hash_prompt
from utils.scoring import DEFAULT_SCORE_SOURCE


logger = logging.getLogger(__name__)
MISSING_TOKEN_RE = re.compile(r"^\s*\[?\s*missing(?::[^\]]*)?\]?\s*$", re.IGNORECASE)


def _is_missing_token(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return True
        if MISSING_TOKEN_RE.match(text):
            return True
    return False


def _strip_missing_tokens_from_list(items: Any) -> list[str]:
    if not isinstance(items, list):
        return []
    out: list[str] = []
    for item in items:
        text = str(item).strip()
        if not _is_missing_token(text):
            out.append(text)
    return out


def _sanitize_structured_signals(signals: Any) -> dict:
    if not isinstance(signals, dict):
        return {}
    cleaned: dict = {}
    for dim, components in signals.items():
        if not isinstance(components, dict):
            continue
        cleaned_components: dict = {}
        for name, comp in components.items():
            if not isinstance(comp, dict):
                continue
            entry = dict(comp)
            if _is_missing_token(entry.get("label")):
                entry.pop("label", None)
                entry["value"] = None
                entry["confidence"] = 0.2
            elif _is_missing_token(entry.get("value")):
                entry["value"] = None
                entry["confidence"] = 0.2
            cleaned_components[name] = entry
        cleaned[dim] = cleaned_components
    return cleaned


_EXPECTED_STRUCTURED_COMPONENTS: Dict[str, tuple[str, ...]] = {
    "market": ("tam", "growth_rate", "urgency", "timing", "competition"),
    "execution": ("traction", "growth_velocity", "gtm_effectiveness", "team_execution", "operational_velocity"),
    "product": ("value_prop", "pain_alignment", "differentiation", "ux", "retention"),
    "technical": ("complexity", "engineering_quality", "scalability", "data_advantage", "architecture"),
    "defensibility": ("network_effects", "switching_costs", "proprietary_data", "barriers", "brand"),
}


def _normalize_structured_signals_contract(data: Dict[str, Any]) -> Dict[str, Any]:
    raw = _sanitize_structured_signals(data.get("structured_signals"))
    out: Dict[str, Any] = {}
    for dim, components in _EXPECTED_STRUCTURED_COMPONENTS.items():
        dim_payload = raw.get(dim, {}) if isinstance(raw.get(dim), dict) else {}
        dim_reasoning = data.get(f"{dim}_reasoning")
        evidence = " ".join(str(x).strip() for x in dim_reasoning if str(x).strip()) if isinstance(dim_reasoning, list) else ""
        out[dim] = {}
        for comp in components:
            item = dim_payload.get(comp, {}) if isinstance(dim_payload.get(comp), dict) else {}
            label = item.get("label")
            value = item.get("value")
            if _is_missing_token(label):
                label = None
            if _is_missing_token(value):
                value = None
            confidence = item.get("confidence")
            try:
                conf = max(0.0, min(1.0, float(confidence)))
            except (TypeError, ValueError):
                conf = 0.2 if label is None and value is None else 0.5
            normalized = {
                "confidence": conf,
                "reasoning": str(item.get("reasoning") or ""),
            }
            if label is not None:
                normalized["label"] = str(label)
            else:
                normalized["value"] = value
            if item.get("evidence") is not None:
                normalized["evidence"] = str(item.get("evidence"))
            elif evidence:
                normalized["evidence"] = evidence
            out[dim][comp] = normalized
    data["structured_signals"] = out
    return data


def _load_reviewer_resources() -> tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Load reviewer rules and evaluation rubric via policy_resolver (active.json + versions).
    """
    from core.policy_resolver import get_evaluation_rubric, get_reviewer_rules

    reviewer_rules = get_reviewer_rules()
    rubric = get_evaluation_rubric()
    return reviewer_rules, rubric


def _build_dimensions_block(rubric: Dict[str, Any]) -> str:
    """Build evaluation dimensions block from rubric (v1.1: question, definition, criteria)."""
    dimensions = rubric.get("dimensions", [])
    if not dimensions:
        return ""
    lines = ["\nEVALUATION DIMENSIONS (score each 1–10; justify against criteria):"]
    for dim in dimensions:
        name = dim.get("name", dim.get("id", ""))
        question = dim.get("question", "")
        definition = dim.get("definition", "")
        lines.append(f"\n{name} ({dim.get('id', '')}):")
        if question:
            lines.append(f"  Question: {question}")
        if definition:
            lines.append(f"  Definition: {definition}")
        high = dim.get("high", {})
        mid = dim.get("mid", {})
        low = dim.get("low", {})
        if high.get("criteria"):
            lines.append(f"  8–10 (Strong): {high['criteria']}")
        if mid.get("criteria"):
            lines.append(f"  5–7 (Promising): {mid['criteria']}")
        if low.get("criteria"):
            lines.append(f"  1–4 (Weak): {low['criteria']}")
    return "\n".join(lines) + "\n"


def _deterministic_scoring_contract_block() -> str:
    """When structured scoring is enabled platform-wide, clarify LLM ints vs authoritative scores."""
    if os.getenv("USE_STRUCTURED_SCORING", "true").lower() not in ("1", "true", "yes"):
        return ""
    return """
DETERMINISTIC SCORING (enabled in deployment):
- Integers market_score … defensibility_score in your JSON are non-authoritative hints for coherence checks only.
- Final published scores are computed deterministically from structured_signals (extraction → normalization → aggregation).
- Prioritize accurate, complete structured_signals and qualitative diligence fields; do not tune integers to disagree with your own signals.
"""


def _build_system_prompt(reviewer_rules: Dict[str, Any], rubric: Dict[str, Any]) -> str:
    """Build system prompt from versioned reviewer rules and evaluation rubric (policy_resolver)."""
    red_flags_block = ""
    if reviewer_rules.get("diligence_red_flags"):
        red_flags_block = "\nDILIGENCE RED FLAGS (use these exact labels in diligence_red_flags):\n"
        for rf in reviewer_rules["diligence_red_flags"]:
            label = rf.get("label", rf.get("id", ""))
            red_flags_block += f"- {label}\n"
    elif rubric.get("red_flags"):
        red_flags_block = "\nDILIGENCE RED FLAGS (use these exact labels in diligence_red_flags):\n"
        for rf in rubric["red_flags"]:
            label = rf.get("label", rf.get("id", ""))
            red_flags_block += f"- {label}\n"

    dimensions_block = _build_dimensions_block(rubric)

    return f"""You are a Reviewer for a venture capital firm.

Your role is to evaluate startup ideas discovered by Scout agents.

You are:
- Conservative and analytical
- Focused on quality, realism, and fundability
- Tasked with filtering noise early
- Skeptical of missing data

SCORE BANDS (apply uniformly): 1–3 Weak; 4–5 Concerning; 6–7 Promising; 8–10 Strong.
Rule of thumb: 5 = neutral/unproven; 6–7 = promising but incomplete; 8+ = fundable if pricing & ownership make sense.
{dimensions_block}
VERDICT (derived from scores, not subjective):
- STRONG: avg ≥ 8.0, no dimension < 7, zero critical red flags
- MEDIUM: avg ≥ 6.0, no dimension < 5 (max one exception), execution risk acceptable but unresolved
- WEAK: avg < 6.0 OR multiple dimensions < 5 OR critical red flag present

NARRATIVE AND SCORING:
- overall_summary must be a concise narrative synthesis for the investment committee. Do NOT list or repeat numeric scores in overall_summary (scores are captured in the scores table and score_reasoning). Write 2-4 sentences summarizing strengths, concerns, and fit; no "X/10" or score phrases in this field.
- Extract structured_signals as strict JSON evidence with confidences; deterministic scoring runs downstream and sets final scores.
{_deterministic_scoring_contract_block()}
- Use bullet points for positives and risks where appropriate. Provide 2-5 bullets per analysis list when content allows.
- Never emit placeholder strings like [MISSING]. When information is absent, leave list fields empty and rely on confidence + structured_signals null values.
- Do NOT invent data; only summarize what the Scout provides.

HYPOTHESIS-DRIVEN EVALUATION:
- Consume Scout hypothesis fields: primary_thesis, key_assumptions, biggest_unknown (when provided).
- In assumption_feedback: comment on which assumptions are well-supported or weak; highlight critical unknowns that could invalidate the thesis.
- Use only information provided or defined in resources. Do NOT hallucinate missing data.

{red_flags_block}

You do NOT:
- Generate new ideas
- Search externally
- Make assumptions beyond what's provided
- Hallucinate missing data

Be honest and critical. Most ideas should score in the 4-7 range.
Only truly exceptional opportunities should score 8+. Output ONLY valid JSON; no text before or after."""


def _format_scout_context_extras(scout_output: Dict[str, Any]) -> str:
    """Compact factual scout fields for the reviewer user message (matches ReviewerEngine payload)."""
    from urllib.parse import urlparse

    lines: list[str] = []
    st = scout_output.get("scout_type")
    if st:
        lines.append(f"Scout type: {st}")
    fs = scout_output.get("funding_stage")
    if fs:
        lines.append(f"Funding stage (scout): {fs}")
    et = scout_output.get("est_tam")
    if et:
        lines.append(f"Est. TAM (scout): {et}")
    refs = scout_output.get("references")
    if isinstance(refs, list) and refs:
        hosts: list[str] = []
        for r in refs[:12]:
            if not isinstance(r, str) or not r.strip():
                continue
            raw = r.strip()
            url = raw if raw.startswith(("http://", "https://")) else f"https://{raw.split('/')[0]}"
            try:
                host = (urlparse(url).hostname or "").lower()
                if host and host not in hosts:
                    hosts.append(host)
            except Exception:
                continue
            if len(hosts) >= 8:
                break
        host_part = ", ".join(hosts[:6]) if hosts else "(unparsed URLs)"
        lines.append(f"References: {len(refs)} item(s); hostnames: {host_part}")
    for lk in ("lookup_id", "lookup_query", "origin_type"):
        v = scout_output.get(lk)
        if v is not None and str(v).strip():
            lines.append(f"{lk}: {str(v).strip()[:240]}")
    if not lines:
        return ""
    return "\nScout context (factual — ground structured_signals here):\n" + "\n".join(lines) + "\n"


class Reviewer(ABC):
    """
    Base class for Reviewer agents.
    
    Reviewers:
    - Evaluate Scout discoveries (do NOT generate ideas)
    - Are conservative and analytical
    - Filter noise early
    - Make one LLM call per evaluation
    - Emit validated JSON output
    - Use /resources for rules and red flag definitions
    """
    
    SYSTEM_PROMPT: str = ""  # Set in __init__ from resources

    def __init__(self, api_key: str, model: str = "gpt-5-nano", tenant_user_id: str = ""):
        """
        Initialize a Reviewer.
        
        Args:
            api_key: OpenAI API key
            model: OpenAI model to use (default: gpt-5-nano)
            tenant_user_id: Clerk user id for loading promoted prompts from Supabase
        """
        self.client = OpenAI(api_key=api_key)
        self.logger = logging.getLogger("reviewer")
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.model = model
        self._last_token_usage = 0
        self._tenant_user_id = (tenant_user_id or "").strip()
        reviewer_rules, rubric = _load_reviewer_resources()
        self.SYSTEM_PROMPT = _build_system_prompt(reviewer_rules, rubric)
        self.reviewer_type = getattr(self, 'reviewer_type', 'default')
        self.agent_name = self._get_agent_name()
        self._load_prompt_from_library()
        self._fund_thesis_ctx: Optional[Dict[str, Any]] = None

    def set_fund_thesis(self, thesis_ctx: Optional[Dict[str, Any]]) -> None:
        """Runtime mandate from Supabase active thesis; None clears."""
        self._fund_thesis_ctx = thesis_ctx

    def _get_agent_name(self) -> str:
        """Map reviewer_type to agent name for prompt library lookup."""
        mapping = {
            "default": "DefaultReviewer",
            "skeptical": "SkepticalReviewer",
            "opportunist": "OpportunistReviewer",
        }
        return mapping.get(self.reviewer_type, "DefaultReviewer")

    def _load_prompt_from_library(self) -> None:
        """Load promoted prompt from Supabase when enabled; else latest local library file."""
        use_sb = os.getenv("USE_SUPABASE_STORAGE", "").lower() in ("1", "true", "yes")
        if use_sb and self._tenant_user_id:
            try:
                from meta.prompt_gating import load_prompt_active, load_prompt_library

                library = load_prompt_library(self._tenant_user_id)
                active = load_prompt_active(self._tenant_user_id)
                key = active.get(self.agent_name)
                if (
                    key
                    and library.get(key)
                    and isinstance(library[key], dict)
                    and library[key].get("prompt")
                ):
                    self.SYSTEM_PROMPT = str(library[key]["prompt"])
                    self.logger.info("Loaded promoted reviewer prompt from Supabase: %s", key)
                    return
            except Exception as e:
                self.logger.debug("Could not load reviewer prompt from Supabase: %s", e)
        try:
            lib_path = Path(__file__).resolve().parent.parent / "data" / "meta" / "prompt_library.json"
            if not lib_path.exists():
                return
            with open(lib_path, "r") as f:
                library = json.load(f)
            if not isinstance(library, dict):
                return
            latest_key = None
            latest_time = ""
            for key, entry in library.items():
                if key.startswith(self.agent_name + ":"):
                    created = entry.get("created_at", "")
                    if created > latest_time:
                        latest_time = created
                        latest_key = key
            if latest_key and library[latest_key].get("prompt"):
                self.SYSTEM_PROMPT = library[latest_key]["prompt"]
                self.logger.info(f"Loaded prompt from library: {latest_key}")
        except Exception as e:
            self.logger.debug(f"Could not load prompt from library: {e}")

    def set_prompt(self, new_prompt: str) -> None:
        """Set a new system prompt (called by MetaAgent)."""
        self.SYSTEM_PROMPT = new_prompt
        self.logger.info(f"Prompt updated for {self.agent_name} ({hash_prompt(new_prompt)})")
    
    async def review(self, scout_output: dict) -> Optional[ReviewerOutput]:
        """
        Review a Scout discovery.
        
        Args:
            scout_output: Valid ScoutOutput dict
        
        Returns:
            ReviewerOutput if review succeeds, None if it fails.
        """
        data = await self._call_llm(scout_output)
        if data is None:
            return None
        
        try:
            validated = validate_reviewer_output(data)
            return validated
        except ValueError as e:
            self.logger.error(f"Validation failed: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Review failed: {e}")
            return None
    
    def _call_llm_sync(self, scout_output: dict) -> Optional[dict]:
        """
        Synchronous LLM call to review a Scout discovery.
        Includes Scout hypothesis fields (primary_thesis, key_assumptions, biggest_unknown)
        when present; handles null/absent gracefully.
        
        Args:
            scout_output: Valid ScoutOutput dict (may include hypothesis fields or not)
        
        Returns:
            Parsed JSON dict if successful, None if failed.
        """
        try:
            # Format Scout output for the prompt (core fields)
            scout_text = f"""
Company: {scout_output.get('name', 'Unknown')}
One-line: {scout_output.get('one_line', 'N/A')}
Sector: {scout_output.get('sector', 'N/A')}
Problem: {scout_output.get('problem', 'N/A')}
Solution: {scout_output.get('solution', 'N/A')}
Target Users: {scout_output.get('target_users', 'N/A')}
Why Now: {scout_output.get('why_now', 'N/A')}
Scout Confidence: {scout_output.get('confidence', 0.0):.2f}
"""
            scout_text += _format_scout_context_extras(scout_output)
            # Hypothesis fields: include when present; otherwise omit or show N/A
            primary_thesis = scout_output.get("primary_thesis")
            key_assumptions = scout_output.get("key_assumptions")
            biggest_unknown = scout_output.get("biggest_unknown")
            if primary_thesis is not None or key_assumptions is not None or biggest_unknown is not None:
                scout_text += "\nScout hypothesis (review and comment in assumption_feedback):\n"
                scout_text += f"Primary thesis: {primary_thesis if primary_thesis else 'N/A'}\n"
                if isinstance(key_assumptions, list):
                    scout_text += f"Key assumptions: {json.dumps(key_assumptions)}\n"
                else:
                    scout_text += "Key assumptions: N/A\n"
                scout_text += f"Biggest unknown: {biggest_unknown if biggest_unknown else 'N/A'}\n"

            try:
                from core.fund_thesis_resolver import format_fund_thesis_context_for_prompt

                resource_thesis_block = format_fund_thesis_context_for_prompt()
            except Exception:
                resource_thesis_block = ""

            thesis_block = ""
            ctx = getattr(self, "_fund_thesis_ctx", None)
            if ctx:
                pj = ctx.get("parsed_json") or {}
                raw = str(ctx.get("raw_text") or "").strip()
                summary = raw[:4000] if len(raw) > 4000 else raw
                thesis_block = (
                    "\n\nFUND THESIS MANDATE (required — score this opportunity against this mandate; "
                    "reasoning in score_reasoning should reference fit vs thesis where relevant):\n"
                    f"active_thesis_version_id: {ctx.get('version_id', '')}\n"
                )
                if summary:
                    thesis_block += f"thesis_summary (plain text):\n{summary}\n\n"
                thesis_block += f"structured_mandate (JSON):\n{json.dumps(pj, ensure_ascii=False)[:12000]}\n"
                emb = ctx.get("embedding") or []
                if isinstance(emb, list) and emb:
                    thesis_block += (
                        f"thesis_embedding_model: {ctx.get('embedding_model', '')}\n"
                        f"thesis_embedding_dim: {len(emb)}\n"
                        f"thesis_embedding_preview (first 24 floats, numerical grounding): "
                        f"{json.dumps([round(float(x), 6) for x in emb[:24]])}\n"
                    )
            
            json_schema = '''{
  "structured_signals": { // required: extraction-only evidence used by deterministic scorer
    "market": {
      "tam": {"value": "€12B", "confidence": 0.7, "reasoning": "Market sizing source", "evidence": "quote"},
      "growth_rate": {"value": "18%", "confidence": 0.6, "reasoning": "Growth estimate basis", "evidence": "quote"},
      "urgency": {"label": "high", "confidence": 0.8, "reasoning": "Urgency basis", "evidence": "quote"},
      "timing": {"label": "favorable", "confidence": 0.7, "reasoning": "Timing basis", "evidence": "quote"},
      "competition": {"label": "moderate", "confidence": 0.7, "reasoning": "Competition basis", "evidence": "quote"}
    },
    "execution": {
      "traction": {"label": "early_revenue", "confidence": 0.6, "reasoning": "...", "evidence": "..."},
      "growth_velocity": {"label": "moderate", "confidence": 0.6, "reasoning": "...", "evidence": "..."},
      "gtm_effectiveness": {"label": "repeatable", "confidence": 0.6, "reasoning": "...", "evidence": "..."},
      "team_execution": {"label": "decent", "confidence": 0.6, "reasoning": "...", "evidence": "..."},
      "operational_velocity": {"label": "moderate", "confidence": 0.6, "reasoning": "...", "evidence": "..."}
    },
    "product": {
      "value_prop": {"label": "clear", "confidence": 0.6, "reasoning": "...", "evidence": "..."},
      "pain_alignment": {"label": "strong", "confidence": 0.6, "reasoning": "...", "evidence": "..."},
      "differentiation": {"label": "clear", "confidence": 0.6, "reasoning": "...", "evidence": "..."},
      "ux": {"label": "usable", "confidence": 0.6, "reasoning": "...", "evidence": "..."},
      "retention": {"label": "moderate", "confidence": 0.6, "reasoning": "...", "evidence": "..."}
    },
    "technical": {
      "complexity": {"label": "moderate", "confidence": 0.6, "reasoning": "...", "evidence": "..."},
      "engineering_quality": {"label": "decent", "confidence": 0.6, "reasoning": "...", "evidence": "..."},
      "scalability": {"label": "medium", "confidence": 0.6, "reasoning": "...", "evidence": "..."},
      "data_advantage": {"label": "limited", "confidence": 0.6, "reasoning": "...", "evidence": "..."},
      "architecture": {"label": "early", "confidence": 0.6, "reasoning": "...", "evidence": "..."}
    },
    "defensibility": {
      "network_effects": {"label": "moderate", "confidence": 0.6, "reasoning": "...", "evidence": "..."},
      "switching_costs": {"label": "medium", "confidence": 0.6, "reasoning": "...", "evidence": "..."},
      "proprietary_data": {"label": "some", "confidence": 0.6, "reasoning": "...", "evidence": "..."},
      "barriers": {"label": "some", "confidence": 0.6, "reasoning": "...", "evidence": "..."},
      "brand": {"label": "emerging", "confidence": 0.6, "reasoning": "...", "evidence": "..."}
    }
  },
  "market_score": int,        // 1-10
  "product_score": int,       // 1-10
  "technical_score": int,     // 1-10
  "execution_score": int,     // 1-10 (emphasize team)
  "defensibility_score": int, // 1-10 (moats, network effects, etc.)
  "overall_summary": "string",  // Narrative synthesis for IC; do NOT list scores (e.g. no "Market 7/10: ..."); scores go in score_reasoning
  "key_risks": ["string", "..."],
  "verdict": "STRONG" | "MEDIUM" | "WEAK",
  "diligence_red_flags": ["string", "..."],  // Use only labels from versioned reviewer_rules policy
  "assumption_feedback": ["string", "..."],  // Comments on Scout assumptions; critical unknowns
  "team_analysis": ["string", "..."],        // Optional: founders, roles, experience, unfair advantage; [] if absent
  "competition_analysis": ["string", "..."], // Optional: competitors, market position, differentiation, SWOT bullets
  "business_model_analysis": ["string", "..."], // Optional: monetization, pricing, growth plan, unit economics; [] if absent
  "investment_thesis": ["string", "..."],    // Optional: bullet points why to invest + core assumptions
  "risk_mitigation": ["string", "..."],     // Optional: actionable strategies for each diligence_red_flags item
  "score_reasoning": {"market_score": "string", "product_score": "string", ...},  // Optional: concise reasoning per dimension for memo table
  "market_reasoning": ["string", "..."],      // 2-4 bullets
  "market_weaknesses": ["string", "..."],     // 1-3 bullets
  "market_confidence": "low" | "medium" | "high",
  "product_reasoning": ["string", "..."],     // 2-4 bullets
  "product_weaknesses": ["string", "..."],    // 1-3 bullets
  "product_confidence": "low" | "medium" | "high",
  "technical_reasoning": ["string", "..."],   // 2-4 bullets
  "technical_weaknesses": ["string", "..."],  // 1-3 bullets
  "technical_confidence": "low" | "medium" | "high",
  "execution_reasoning": ["string", "..."],   // 2-4 bullets
  "execution_weaknesses": ["string", "..."],  // 1-3 bullets
  "execution_confidence": "low" | "medium" | "high",
  "defensibility_reasoning": ["string", "..."],  // 2-4 bullets
  "defensibility_weaknesses": ["string", "..."], // 1-3 bullets
  "defensibility_confidence": "low" | "medium" | "high",
  "improvement_to_9": ["string", "..."],      // Specific steps that could lift this to 9/10 quality
  "score_source": "string",                   // Explain score provenance
  "thesis_alignment_score": number,  // 0.0-1.0 fit to fund thesis mandate (required when FUND THESIS MANDATE section present)
  "thesis_matches_fund": boolean,     // true if clearly aligned with mandate
  "thesis_fit_points": ["string"],   // concise bullets: why it fits
  "thesis_deviation_points": ["string"], // concise bullets: where it diverges
  "thesis_alignment_confidence": number // 0.0-1.0 confidence in alignment judgment
}'''
            
            user_content = (
                f"Evaluate this startup idea discovered by a Scout:\n\n{scout_text}{resource_thesis_block}{thesis_block}\n\n"
                "Review Scout hypotheses when provided: evaluate assumptions and flag critical unknowns in assumption_feedback. "
                "Use only information provided or defined in resources; do not hallucinate missing data. "
                "CRITICAL: treat all numeric score fields as provisional placeholders only. "
                "Do not invent final scoring. Your primary responsibility is to extract structured_signals with confidence values. "
                "structured_signals must be COMPLETE: include all 5 dimensions and all 25 components (no empty objects). "
                "For each component provide either label or value, plus reasoning and evidence grounded in the provided startup text. "
                "If evidence is unavailable, set value to null with confidence <= 0.2 and explain what is missing in reasoning. "
                "In overall_summary, write a concise narrative synthesis only; do not list or repeat numeric scores (scores are in score_reasoning). "
                "Emphasize team in execution_score; if team/founder data is missing, say so plainly and leave team_analysis as an empty list. "
                "Populate team_analysis, competition_analysis, business_model_analysis, investment_thesis, and risk_mitigation when you can; use empty lists when info is absent. "
                "Optionally include score_reasoning with one short sentence per dimension (e.g. market_score, product_score, technical_score, execution_score, defensibility_score) for the memo scores table.\n\n"
                "For each dimension, include 2-4 reasoning bullets, 1-3 weaknesses bullets, and confidence as one of low/medium/high. "
                "Include improvement_to_9 as actionable bullets and set score_source to reflect multi-reviewer aggregation.\n\n"
                f"Output ONLY valid JSON matching this exact schema:\n\n{json_schema}\n\n"
                "If founding team, revenue, competitors, or valuation data is missing, add the exact red-flag labels to diligence_red_flags. "
                "Do not include any text before or after the JSON. Output only the JSON object."
            )
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": user_content},
                ],
                response_format={"type": "json_object"},
                max_completion_tokens=8192,
            )
            
            if hasattr(response, 'usage') and response.usage:
                self._last_token_usage = getattr(response.usage, 'total_tokens', 0) or 0
            else:
                self._last_token_usage = 0

            content = response.choices[0].message.content
            if not content:
                self.logger.error("Empty response from LLM")
                return None
            
            # Parse JSON
            data = json.loads(content)
            
            # Default optional fields
            if "structured_signals" not in data or not isinstance(data.get("structured_signals"), dict):
                data["structured_signals"] = {}
            data = _normalize_structured_signals_contract(data)
            if "defensibility_score" not in data:
                data["defensibility_score"] = None
            if "diligence_red_flags" not in data:
                data["diligence_red_flags"] = []
            if "assumption_feedback" not in data or not isinstance(data.get("assumption_feedback"), list):
                data["assumption_feedback"] = []
            for field in ("team_analysis", "competition_analysis", "business_model_analysis", "investment_thesis", "risk_mitigation"):
                if field not in data or not isinstance(data.get(field), list):
                    data[field] = []
                data[field] = _strip_missing_tokens_from_list(data.get(field))
            if "score_reasoning" not in data or not isinstance(data.get("score_reasoning"), dict):
                data["score_reasoning"] = {}
            if "score_source" not in data or not isinstance(data.get("score_source"), str):
                data["score_source"] = DEFAULT_SCORE_SOURCE
            if "improvement_to_9" not in data or not isinstance(data.get("improvement_to_9"), list):
                data["improvement_to_9"] = []
            for dim in ("market", "product", "technical", "execution", "defensibility"):
                rk = f"{dim}_reasoning"
                wk = f"{dim}_weaknesses"
                ck = f"{dim}_confidence"
                if rk not in data or not isinstance(data.get(rk), list):
                    data[rk] = []
                if wk not in data or not isinstance(data.get(wk), list):
                    data[wk] = []
                data[rk] = _strip_missing_tokens_from_list(data.get(rk))
                data[wk] = _strip_missing_tokens_from_list(data.get(wk))
                if ck not in data or str(data.get(ck)).lower() not in ("low", "medium", "high"):
                    data[ck] = "medium"
            if ctx:
                for key, default in (
                    ("thesis_alignment_score", None),
                    ("thesis_matches_fund", None),
                    ("thesis_fit_points", []),
                    ("thesis_deviation_points", []),
                    ("thesis_alignment_confidence", None),
                ):
                    if key not in data:
                        data[key] = default
                if not isinstance(data.get("thesis_fit_points"), list):
                    data["thesis_fit_points"] = []
                if not isinstance(data.get("thesis_deviation_points"), list):
                    data["thesis_deviation_points"] = []
                for lp in ("thesis_fit_points", "thesis_deviation_points"):
                    data[lp] = [str(x) for x in data[lp] if str(x).strip()][:12]
                ts = data.get("thesis_alignment_score")
                if ts is not None:
                    try:
                        data["thesis_alignment_score"] = max(0.0, min(1.0, float(ts)))
                    except (TypeError, ValueError):
                        data["thesis_alignment_score"] = None
                tc = data.get("thesis_alignment_confidence")
                if tc is not None:
                    try:
                        data["thesis_alignment_confidence"] = max(0.0, min(1.0, float(tc)))
                    except (TypeError, ValueError):
                        data["thesis_alignment_confidence"] = None
                if data.get("thesis_matches_fund") is not None and not isinstance(
                    data.get("thesis_matches_fund"), bool
                ):
                    data["thesis_matches_fund"] = str(data["thesis_matches_fund"]).lower() in (
                        "true",
                        "1",
                        "yes",
                    )
            
            data["prompt_version"] = hash_prompt(self.SYSTEM_PROMPT)
            
            return data
            
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse JSON from LLM: {e}")
            return None
        except Exception as e:
            self.logger.error(f"LLM call failed: {e}")
            return None
    
    async def _call_llm(self, scout_output: dict) -> Optional[dict]:
        """
        Async wrapper for LLM call (runs sync call in thread pool).
        
        Args:
            scout_output: Valid ScoutOutput dict
        
        Returns:
            Parsed JSON dict if successful, None if failed.
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.executor,
            self._call_llm_sync,
            scout_output,
        )
