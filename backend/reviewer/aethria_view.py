"""
Template-only synthesis of a single committee-facing view from persisted review fields.

Does not call LLMs — avoids contradicting stored scores.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set

from models import AethriaView

_TOKEN_RE = re.compile(r"[a-z0-9]{3,}", re.IGNORECASE)


def _tokens(text: str) -> Set[str]:
    return {m.group(0).lower() for m in _TOKEN_RE.finditer(text or "")}


def _is_redundant_with_summary(line: str, overall_summary: str, *, jaccard_min: float = 0.55) -> bool:
    """True when the fit line largely repeats the executive summary (word overlap)."""
    a, b = _tokens(line), _tokens(overall_summary)
    if len(a) < 4 or len(b) < 6:
        return False
    inter = len(a & b)
    union = len(a | b)
    if union == 0:
        return False
    if inter / union >= jaccard_min:
        return True
    # Substring: short line fully contained in summary normalized
    ln = re.sub(r"\s+", " ", (line or "").lower().strip())
    sn = re.sub(r"\s+", " ", (overall_summary or "").lower().strip())
    return len(ln) >= 40 and ln in sn


def _pick_thesis_fit_line(review_output: Dict[str, Any]) -> str:
    fit_pts = review_output.get("thesis_fit_points") or []
    dev_pts = review_output.get("thesis_deviation_points") or []
    summary = (review_output.get("overall_summary") or "").strip()

    if isinstance(fit_pts, list) and fit_pts:
        for raw in fit_pts:
            line = str(raw).strip()
            if not line:
                continue
            if summary and _is_redundant_with_summary(line, summary):
                continue
            return line
        # All fit points redundant with summary — prefer deviation if any
        if isinstance(dev_pts, list) and dev_pts:
            return f"Mandate tension: {str(dev_pts[0]).strip()}"
        return ""

    if isinstance(dev_pts, list) and dev_pts:
        return f"Mandate tension: {str(dev_pts[0]).strip()}"

    return "Thesis alignment: see structured scoring and diligence sections."


def _pick_tension_summary(
    review_output: Dict[str, Any],
    consensus: Dict[str, Any],
    resolution_notes: Optional[List[str]],
) -> str:
    notes = resolution_notes or []
    ds = review_output.get("disagreement_summary")
    if isinstance(ds, str) and ds.strip():
        parts = [ds.strip()]
        blob = parts[0].lower()
        for n in notes[:3]:
            s = str(n).strip()
            if s and s.lower() not in blob:
                parts.append(s)
        return " ".join(parts)[:1200]

    parts: List[str] = []
    if consensus.get("reviewer_disagreement"):
        parts.append("Reviewer personas disagreed on verdict or scores.")
    for n in notes[:3]:
        s = str(n).strip()
        if s and s not in parts:
            parts.append(s)

    if parts:
        return " ".join(parts)[:1200]

    return "No major cross-persona tension flagged beyond normal diligence variance."


_DIM_LABELS = (
    ("market", "market_score"),
    ("product", "product_score"),
    ("technical", "technical_score"),
    ("execution", "execution_score"),
    ("defensibility", "defensibility_score"),
)


def _pick_focal_question(review_output: Dict[str, Any]) -> str:
    dev_pts = review_output.get("thesis_deviation_points") or []
    if isinstance(dev_pts, list) and dev_pts:
        d0 = str(dev_pts[0]).strip()
        if d0:
            return f"Mandate gap to resolve: {d0}"[:500]

    weakest: Optional[tuple[str, str, int]] = None
    for label, key in _DIM_LABELS:
        v = review_output.get(key)
        if not isinstance(v, (int, float)):
            continue
        iv = int(round(float(v)))
        if weakest is None or iv < weakest[2]:
            weakest = (label, key, iv)

    if weakest is not None and weakest[2] <= 6:
        label, key, score = weakest
        sr = review_output.get("score_reasoning") or {}
        blurb = None
        if isinstance(sr, dict):
            blurb = sr.get(key) or sr.get(label) or sr.get(f"{label}_score")
        if isinstance(blurb, str) and blurb.strip():
            return f"Weakest signal ({label}): {blurb.strip()}"[:500]
        return (
            f"What evidence would most improve the {label} narrative "
            f"(currently {score}/10)?"
        )[:500]

    risks = review_output.get("key_risks") or []
    if isinstance(risks, list) and risks:
        return str(risks[0]).strip()[:500]

    return "What evidence would most change conviction on this opportunity?"


def build_aethria_view(
    *,
    review_output: Dict[str, Any],
    scout_output: Dict[str, Any],
    consensus: Dict[str, Any],
    resolution_notes: Optional[List[str]] = None,
) -> AethriaView:
    name = str(scout_output.get("name") or "Company").strip() or "Company"
    headline = f"{name} — Evidence read."
    thesis_fit_line = _pick_thesis_fit_line(review_output)
    tension_summary = _pick_tension_summary(review_output, consensus, resolution_notes)
    focal_question = _pick_focal_question(review_output)

    return AethriaView(
        headline=headline,
        thesis_fit_line=thesis_fit_line[:500],
        tension_summary=tension_summary[:1200],
        focal_question=focal_question[:500],
    )


def polish_aethria_view_for_api(
    aethria_view: Any,
    review: Dict[str, Any],
    company_name: str,
) -> Optional[Dict[str, Any]]:
    """
    Read-time cleanup: fix legacy headlines and drop thesis lines that duplicate executive summary.
    """
    if not isinstance(aethria_view, dict):
        return None
    out = dict(aethria_view)
    name = (company_name or "").strip() or "Company"
    headline = str(out.get("headline") or "").strip()
    hl = headline.lower()
    if "aethria view" in hl:
        out["headline"] = f"{name} — Evidence read."
    tl = str(out.get("thesis_fit_line") or "").strip()
    summ = str(review.get("overall_summary") or "").strip()
    if tl and summ and _is_redundant_with_summary(tl, summ):
        out["thesis_fit_line"] = ""
    return out


def aethria_view_to_dict(view: AethriaView) -> Dict[str, Any]:
    return view.model_dump(mode="json")
