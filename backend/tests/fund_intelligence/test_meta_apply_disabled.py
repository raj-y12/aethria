import pytest

from meta.calibrator import ThresholdCalibrator
from meta.reweighter import ScoutReweighter


def test_legacy_meta_apply_methods_cannot_mutate_production():
    reweighter = object.__new__(ScoutReweighter)
    calibrator = object.__new__(ThresholdCalibrator)
    with pytest.raises(RuntimeError, match="proposal-only"):
        reweighter.apply([{"scout_type": "x", "new_weight": 1}])
    with pytest.raises(RuntimeError, match="proposal-only"):
        calibrator.apply([{"parameter": "x", "new_value": 1}])
