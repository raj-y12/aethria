"""
ThresholdCalibrator — adjusts sensitivity parameters based on calibration warnings.
Deterministic, no LLM.
"""
import json
import logging
import os
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

_BACKEND_DIR = Path(__file__).resolve().parent.parent
_CALIBRATION_PATH = _BACKEND_DIR / "data" / "meta" / "calibration_state.json"
_MUTATION_LOG_PATH = _BACKEND_DIR / "data" / "meta" / "mutation_log.json"

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


def _atomic_write(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    with open(temp, "w") as f:
        json.dump(data, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    temp.replace(path)


def _append_to_json_list(path: Path, entry: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    entries = []
    if path.exists():
        try:
            with open(path, "r") as f:
                entries = json.load(f)
            if not isinstance(entries, list):
                entries = []
        except (json.JSONDecodeError, IOError):
            entries = []
    entries.append(entry)
    _atomic_write(path, entries)


def load_calibration_state() -> Dict[str, Any]:
    """Load current calibration state."""
    if not _CALIBRATION_PATH.exists():
        return dict(DEFAULT_CALIBRATION)
    try:
        with open(_CALIBRATION_PATH, "r") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else dict(DEFAULT_CALIBRATION)
    except (json.JSONDecodeError, IOError):
        return dict(DEFAULT_CALIBRATION)


class ThresholdCalibrator:
    """Adjusts confidence and reviewer thresholds based on calibration warnings."""

    def __init__(self, signal_summary: Dict[str, Any], cycle_number: int):
        self.signal = signal_summary
        self.cycle_number = cycle_number
        self.logger = logging.getLogger("meta.calibrator")
        self.state = load_calibration_state()

    def decide(self) -> List[Dict]:
        """Decide calibration changes. Returns list of CalibrationMutation."""
        reviewer_health = self.signal.get("reviewer_health", {})
        warning = reviewer_health.get("calibration_warning")
        changes = []
        now = datetime.now().isoformat()

        last_cal_cycle = self.state.get("last_calibrated_cycle", 0)
        if (self.cycle_number - last_cal_cycle) < CALIBRATION_PARAM_COOLDOWN and last_cal_cycle > 0:
            self.logger.info("[Calibrator] In cooldown, skipping calibration")
            return []

        from settings_loader import load_settings
        settings = load_settings()
        default_confidence = settings.get("agent_config", {}).get("confidence_threshold", 0.5)

        if warning and "too strict" in warning.lower():
            # Loosen
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
            # Tighten
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
            # No warning — drift overrides back toward defaults
            drifted = False
            ct_override = self.state.get("confidence_threshold_override")
            if ct_override is not None and ct_override != default_confidence:
                delta = 0.02 if ct_override < default_confidence else -0.02
                new_ct = round(ct_override + delta, 3)
                if abs(new_ct - default_confidence) < 0.02:
                    new_ct = None  # Reset to default
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
                drifted = True

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

    @staticmethod
    def apply(changes: List[Dict], cycle_number: int = 0) -> None:
        """Write calibration changes to state and mutation log."""
        if not changes:
            return
        state = load_calibration_state()
        for change in changes:
            param = change["parameter"]
            new_val = change["new_value"]
            if param == "confidence_threshold":
                state["confidence_threshold_override"] = new_val
            elif param == "reviewer_weak_threshold":
                state["reviewer_weak_threshold_override"] = new_val
            elif param == "reviewer_strong_threshold":
                state["reviewer_strong_threshold_override"] = new_val

            state["calibration_history"].append(change)
            _append_to_json_list(_MUTATION_LOG_PATH, {
                "type": "calibration",
                "agent_target": param,
                "cycle_number": change["cycle_number"],
                "applied_at": change["applied_at"],
                "direction": change["direction"],
                "reasoning": change["reasoning"],
            })

        state["last_calibrated_at"] = datetime.now().isoformat()
        state["last_calibrated_cycle"] = cycle_number or (changes[0]["cycle_number"] if changes else 0)
        _atomic_write(_CALIBRATION_PATH, state)
