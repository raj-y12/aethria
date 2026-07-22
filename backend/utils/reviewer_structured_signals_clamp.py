"""
Optional post-LLM clamp on reviewer structured_signals evidence grounding.

When REVIEWER_SIGNALS_STRICT_EVIDENCE=1, downgrades confidence (and optionally clears
labels/values) when evidence does not cite scout narrative or an allowlisted URL.
"""
from __future__ import annotations

import copy
import os
from typing import Any, Dict, List, Mapping, Set

from services.scoring.extraction_layer import EXPECTED_COMPONENTS, _scout_narrative_bundle
from utils.reference_verify import extract_http_urls, normalize_url_for_match


def _truthy(key: str, default: str = "false") -> bool:
    return os.getenv(key, default).strip().lower() in ("1", "true", "yes")


def _allowed_url_keys(scout_output: Dict[str, Any]) -> Set[str]:
    keys: Set[str] = set()
    for r in scout_output.get("references") or []:
        if not isinstance(r, str):
            continue
        for u in extract_http_urls(r):
            k = normalize_url_for_match(u)
            if k:
                keys.add(k)
    for u in scout_output.get("_reviewer_gap_reference_urls") or []:
        if not isinstance(u, str):
            continue
        u = u.strip()
        if not u:
            continue
        if not u.lower().startswith(("http://", "https://")):
            u = "https://" + u.lstrip("/")
        k = normalize_url_for_match(u)
        if k:
            keys.add(k)
    return keys


def _generic_evidence(text: str) -> bool:
    t = text.strip().lower()
    if not t or t in ("n/a", "na", "missing", "none", "unknown"):
        return True
    return False


def _scout_snippets(scout_output: Dict[str, Any]) -> List[str]:
    out: List[str] = []
    for key in ("problem", "solution", "why_now", "one_line", "primary_thesis", "target_users"):
        s = str(scout_output.get(key) or "").strip()
        if len(s) >= 24:
            out.append(s[:280].lower())
    bundle = _scout_narrative_bundle(scout_output).lower()
    if len(bundle) >= 24:
        out.append(bundle[:900])
    return out


def _evidence_mentions_scout(evidence: str, reasoning: str, snippets: List[str]) -> bool:
    blob = f"{evidence} {reasoning}".strip().lower()
    if len(blob) < 8:
        return False
    for snip in snippets:
        if len(snip) >= 20 and snip[:40] in blob:
            return True
        if len(snip) >= 20:
            step = 40
            for i in range(0, max(1, len(snip) - 24), step):
                window = snip[i : i + 28]
                if len(window) >= 20 and window in blob:
                    return True
    return False


def _evidence_has_allowlisted_url(evidence: str, allowed: Set[str]) -> bool:
    for u in extract_http_urls(evidence):
        k = normalize_url_for_match(u)
        if k and k in allowed:
            return True
    return False


def _grounding_settings(
    grounding_contract: Mapping[str, Any] | None,
) -> tuple[bool, bool, float]:
    if grounding_contract is None:
        return (
            _truthy("REVIEWER_SIGNALS_STRICT_EVIDENCE", "true"),
            _truthy("REVIEWER_SIGNALS_STRICT_CLEAR", "true"),
            0.2,
        )
    required = {
        "enabled",
        "clear_ungrounded_labels",
        "ungrounded_confidence_cap",
    }
    if set(grounding_contract) != required:
        raise ValueError("evidence grounding contract is incomplete or has unknown fields")
    enabled = grounding_contract["enabled"]
    clear_labels = grounding_contract["clear_ungrounded_labels"]
    cap = grounding_contract["ungrounded_confidence_cap"]
    if not isinstance(enabled, bool) or not isinstance(clear_labels, bool):
        raise ValueError("evidence grounding flags must be boolean")
    if (
        isinstance(cap, bool)
        or not isinstance(cap, (int, float))
        or not 0 <= float(cap) <= 1
    ):
        raise ValueError("evidence grounding confidence cap must be between 0 and 1")
    return enabled, clear_labels, float(cap)


def clamp_structured_signals_evidence(
    scout_output: Dict[str, Any],
    signals: Any,
    *,
    grounding_contract: Mapping[str, Any] | None = None,
) -> Any:
    """
    Return a deep-copied structured_signals dict with clamped components, or signals unchanged if disabled.
    """
    enabled, clear_labels, confidence_cap = _grounding_settings(
        grounding_contract
    )
    if not enabled:
        return signals
    if not isinstance(signals, dict):
        return signals

    allowed = _allowed_url_keys(scout_output)
    snippets = _scout_snippets(scout_output)
    out = copy.deepcopy(signals)

    for dim, names in EXPECTED_COMPONENTS.items():
        dim_obj = out.get(dim)
        if not isinstance(dim_obj, dict):
            continue
        for name in names:
            comp = dim_obj.get(name)
            if not isinstance(comp, dict):
                continue
            ev = str(comp.get("evidence") or "")
            reason = str(comp.get("reasoning") or "")
            if _generic_evidence(ev) and _generic_evidence(reason):
                continue
            grounded = _evidence_mentions_scout(ev, reason, snippets) or _evidence_has_allowlisted_url(
                ev + " " + reason, allowed
            )
            if grounded:
                continue
            try:
                conf = float(comp.get("confidence", 0.5))
            except (TypeError, ValueError):
                conf = 0.5
            comp["confidence"] = min(conf, confidence_cap)
            if clear_labels:
                comp.pop("label", None)
                comp["value"] = None
            dim_obj[name] = comp
        out[dim] = dim_obj
    return out
