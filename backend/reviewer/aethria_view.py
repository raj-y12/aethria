"""
Template-only synthesis of a single committee-facing view from persisted review fields.

Does not call LLMs — avoids contradicting stored scores.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from models import AethriaView


def build_aethria_view(
    *,
    review_output: Dict[str, Any],
    scout_output: Dict[str, Any],
    consensus: Dict[str, Any],
    resolution_notes: Optional[List[str]] = None,
) -> AethriaView:
    name = str(scout_output.get("name") or "Company").strip() or "Company"
    verdict = review_output.get("derived_verdict") or review_output.get("verdict") or "MEDIUM"
    headline = f"{name}: Aethria view — {verdict}."

    fit_pts = review_output.get("thesis_fit_points") or []
    dev_pts = review_output.get("thesis_deviation_points") or []
    if isinstance(fit_pts, list) and fit_pts:
        thesis_fit_line = str(fit_pts[0]).strip()
    elif isinstance(dev_pts, list) and dev_pts:
        thesis_fit_line = f"Mandate tension: {str(dev_pts[0]).strip()}"
    else:
        thesis_fit_line = "Thesis alignment: see structured scoring and diligence sections."

    tensions: List[str] = []
    if consensus.get("reviewer_disagreement"):
        tensions.append("Reviewer personas disagreed on verdict or scores.")
    notes = resolution_notes or []
    tensions.extend(str(n).strip() for n in notes[:3] if str(n).strip())
    tension_summary = (
        " ".join(tensions)
        if tensions
        else "No major cross-persona tension flagged beyond normal diligence variance."
    )

    risks = review_output.get("key_risks") or []
    if isinstance(risks, list) and risks:
        focal_question = str(risks[0]).strip()
    else:
        focal_question = "What evidence would most change conviction on this opportunity?"

    return AethriaView(
        headline=headline,
        thesis_fit_line=thesis_fit_line[:500],
        tension_summary=tension_summary[:1200],
        focal_question=focal_question[:500],
    )


def aethria_view_to_dict(view: AethriaView) -> Dict[str, Any]:
    return view.model_dump(mode="json")
