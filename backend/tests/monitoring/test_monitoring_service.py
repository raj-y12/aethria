from monitoring.models import RefreshReason, ServiceLevel
from monitoring.service import can_auto_refresh, material_change


def test_archive_and_historical_pass_do_not_auto_refresh():
    assert can_auto_refresh(ServiceLevel.ARCHIVE, RefreshReason.MONITOR_DUE) is False
    assert can_auto_refresh(ServiceLevel.DISCOVERED, RefreshReason.MONITOR_DUE) is False
    assert can_auto_refresh(ServiceLevel.MONITOR, RefreshReason.MONITOR_DUE) is True


def test_explicit_human_refresh_is_allowed_for_non_archived_opportunity():
    assert can_auto_refresh(ServiceLevel.DISCOVERED, RefreshReason.HUMAN_REQUEST) is True
    assert can_auto_refresh(ServiceLevel.ARCHIVE, RefreshReason.HUMAN_REQUEST) is False


def test_material_change_uses_canonical_snapshot_hash_not_page_cosmetics():
    assert material_change("hash-a", "hash-a") is False
    assert material_change("hash-a", "hash-b") is True
    assert material_change(None, "hash-b") is True
