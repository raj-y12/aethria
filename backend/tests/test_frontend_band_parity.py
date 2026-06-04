"""Structural guard for audit B1: the frontend score bands MUST match the canonical
rubric. The B1 fix (Phase 1) aligned them by hand; this test makes any future drift
fail CI instead of silently re-introducing the verdict inversion (a `7` rendering as
"Strong" while the rubric calls it "Promising").

This is the deterministic half of P4.1. The fuller version derives the bands from the
policy payload at runtime so a hand-mirror isn't needed at all.
"""

import json
import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_RUBRIC = _REPO_ROOT / "resources" / "config" / "evaluation_rubric" / "v1.json"
_SEMANTICS = _REPO_ROOT / "app-front-end" / "src" / "design-system" / "semantics.ts"


def _rubric_bands():
    data = json.loads(_RUBRIC.read_text())
    return [(tuple(b["range"]), b["label"]) for b in data["score_bands"]]


def _frontend_bands():
    text = _SEMANTICS.read_text()
    block = re.search(r"export const SCORE_BANDS\s*=\s*\[(.*?)\]\s*as const;", text, re.DOTALL)
    assert block, "Could not locate SCORE_BANDS in semantics.ts"
    bands = []
    for m in re.finditer(
        r"range:\s*\[\s*(\d+)\s*,\s*(\d+)\s*\].*?label:\s*'([^']+)'",
        block.group(1),
    ):
        lo, hi, label = int(m.group(1)), int(m.group(2)), m.group(3)
        bands.append(((lo, hi), label))
    return bands


def test_frontend_score_bands_match_rubric_B1():
    rubric = _rubric_bands()
    frontend = _frontend_bands()
    assert frontend == rubric, (
        "Frontend SCORE_BANDS drifted from the canonical rubric (audit B1).\n"
        f"  rubric:   {rubric}\n  frontend: {frontend}\n"
        "Re-align app-front-end/src/design-system/semantics.ts with "
        "resources/config/evaluation_rubric/v1.json."
    )


def test_every_integer_score_maps_to_the_same_band_both_sides_B1():
    """Belt-and-suspenders: for scores 1..10 the rubric band and the frontend band
    (per its [lo, hi] ranges) agree — the exact property that was violated before."""
    rubric = _rubric_bands()
    frontend = _frontend_bands()

    def band_for(bands, score):
        for (lo, hi), label in bands:
            if lo <= score <= hi:
                return label
        return None

    for score in range(1, 11):
        assert band_for(frontend, score) == band_for(rubric, score), (
            f"score {score}: frontend={band_for(frontend, score)} "
            f"rubric={band_for(rubric, score)}"
        )
