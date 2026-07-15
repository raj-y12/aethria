"""
ThresholdCalibrator — adjusts sensitivity parameters based on calibration warnings.
Backed by Supabase meta_calibration_state and meta_mutation_log (explicit user_id).
"""
import logging
import os
from typing import Dict, Any, List
from datetime import datetime
from utils.timeutil import utcnow

from supabase_doc_store import doc_get, doc_set, list_append_only

logger = logging.getLogger(__name__)

_CALIBRATION_TABLE = "meta_calibration_state"
_MUTATION_LOG_TABLE = "meta_mutation_log"

CONFIDENCE_FLOOR = 0.2
CONFIDENCE_CEILING = 0.8
THRESHOLD_MAX_OFFSET = 1.0

DEFAULT_CALIBRATION = {
    "confidence_threshold_override": None,
    "reviewer_weak_threshold_override": None,
    "reviewer_strong_threshold_override": None,
    "last_calibrated_at": None,
    "last_calibrated_cycle": 0,
    "calibration_history": [],
}

CALIBRATION_COOLDOWN_CYCLES = int(os.getenv("META_AGENT_MUTATION_COOLDOWN_CYCLES", "3"))
CALIBRATION_PARAM_COOLDOWN = 5


def load_calibration_state(user_id: str) -> Dict[str, Any]:
    data = doc_get(_CALIBRATION_TABLE, user_id=user_id)
    return data if isinstance(data, dict) else dict(DEFAULT_CALIBRATION)


class ThresholdCalibrator:
    """Adjusts confidence and reviewer thresholds based on calibration warnings."""

    def __init__(self, signal_summary: Dict[str, Any], cycle_number: int, user_id: str):
        self.signal = signal_summary
        self.cycle_number = cycle_number
        self.user_id = user_id
        self.logger = logging.getLogger("meta.calibrator")
        self.state = load_calibration_state(user_id)

    def decide(self) -> List[Dict]:
        reviewer_health = self.signal.get("reviewer_health", {})
        warning = reviewer_health.get("calibration_warning")
        changes = []
        now = utcnow().isoformat()

        last_cal_cycle = self.state.get("last_calibrated_cycle", 0)
        if (self.cycle_number - last_cal_cycle) < CALIBRATION_PARAM_COOLDOWN and last_cal_cycle > 0:
            self.logger.info("[Calibrator] In cooldown, skipping calibration")
            return []

        from utils.settings_loader import load_settings

        settings = load_settings(self.user_id)
        default_confidence = settings.get("agent_config", {}).get("confidence_threshold", 0.5)

        if warning and "too strict" in warning.lower():
            current_ct = self.state.get("confidence_threshold_override") or default_confidence
            new_ct = max(CONFIDENCE_FLOOR, round(current_ct - 0.05, 3))
            if new_ct != current_ct:
                changes.append({
                    "parameter": "confidence_threshold",
                    "previous_value": current_ct,
                    "new_value": new_ct,
                    "direction": "loosened",
                    "reasoning": "Calibration warning: thresholds too strict, loosening confidence threshold",
                    "triggered_by": warning,
                    "applied_at": now,
                    "cycle_number": self.cycle_number,
                })

            current_wt = self.state.get("reviewer_weak_threshold_override")
            default_weak = 6.0
            current_wt = current_wt if current_wt is not None else default_weak
            new_wt = max(default_weak - THRESHOLD_MAX_OFFSET, round(current_wt - 0.3, 2))
            if new_wt != current_wt:
                changes.append({
                    "parameter": "reviewer_weak_threshold",
                    "previous_value": current_wt,
                    "new_value": new_wt,
                    "direction": "loosened",
                    "reasoning": "Calibration warning: too many WEAK verdicts, lowering threshold",
                    "triggered_by": warning,
                    "applied_at": now,
                    "cycle_number": self.cycle_number,
                })

        elif warning and "too lenient" in warning.lower():
            current_ct = self.state.get("confidence_threshold_override") or default_confidence
            new_ct = min(CONFIDENCE_CEILING, round(current_ct + 0.05, 3))
            if new_ct != current_ct:
                changes.append({
                    "parameter": "confidence_threshold",
                    "previous_value": current_ct,
                    "new_value": new_ct,
                    "direction": "tightened",
                    "reasoning": "Calibration warning: thresholds too lenient, tightening confidence",
                    "triggered_by": warning,
                    "applied_at": now,
                    "cycle_number": self.cycle_number,
                })

            current_wt = self.state.get("reviewer_weak_threshold_override")
            default_weak = 6.0
            current_wt = current_wt if current_wt is not None else default_weak
            new_wt = min(default_weak + THRESHOLD_MAX_OFFSET, round(current_wt + 0.3, 2))
            if new_wt != current_wt:
                changes.append({
                    "parameter": "reviewer_weak_threshold",
                    "previous_value": current_wt,
                    "new_value": new_wt,
                    "direction": "tightened",
                    "reasoning": "Calibration warning: too many STRONG verdicts, raising threshold",
                    "triggered_by": warning,
                    "applied_at": now,
                    "cycle_number": self.cycle_number,
                })

        else:
            ct_override = self.state.get("confidence_threshold_override")
            if ct_override is not None and ct_override != default_confidence:
                delta = 0.02 if ct_override < default_confidence else -0.02
                new_ct = round(ct_override + delta, 3)
                if abs(new_ct - default_confidence) < 0.02:
                    new_ct = None
                changes.append({
                    "parameter": "confidence_threshold",
                    "previous_value": ct_override,
                    "new_value": new_ct if new_ct is not None else default_confidence,
                    "direction": "reset_drift",
                    "reasoning": "No calibration warning, drifting toward default",
                    "triggered_by": "healthy_system",
                    "applied_at": now,
                    "cycle_number": self.cycle_number,
                })

            wt_override = self.state.get("reviewer_weak_threshold_override")
            default_weak = 6.0
            if wt_override is not None and wt_override != default_weak:
                delta = 0.02 if wt_override < default_weak else -0.02
                new_wt = round(wt_override + delta, 2)
                if abs(new_wt - default_weak) < 0.02:
                    new_wt = None
                changes.append({
                    "parameter": "reviewer_weak_threshold",
                    "previous_value": wt_override,
                    "new_value": new_wt if new_wt is not None else default_weak,
                    "direction": "reset_drift",
                    "reasoning": "No calibration warning, drifting toward default",
                    "triggered_by": "healthy_system",
                    "applied_at": now,
                    "cycle_number": self.cycle_number,
                })

        return changes

    def apply(self, changes: List[Dict]) -> None:
        if not changes:
            return
        raise RuntimeError("Threshold calibration is proposal-only; publish through Fund Intelligence")
