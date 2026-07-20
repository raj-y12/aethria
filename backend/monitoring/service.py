from monitoring.models import RefreshReason, ServiceLevel


def can_auto_refresh(
    service_level: ServiceLevel | int, reason: RefreshReason | str
) -> bool:
    level = ServiceLevel(service_level)
    trigger = RefreshReason(reason)
    if level is ServiceLevel.ARCHIVE:
        return False
    if trigger is RefreshReason.HUMAN_REQUEST:
        return True
    if trigger is RefreshReason.MONITOR_DUE:
        return level >= ServiceLevel.MONITOR
    if trigger in {
        RefreshReason.STALE_DECISIVE_EVIDENCE,
        RefreshReason.MISSING_POLICY_EVIDENCE,
        RefreshReason.CLAIM_CORRECTION,
        RefreshReason.POLICY_CHANGE,
    }:
        return level >= ServiceLevel.ACTIVE_REVIEW
    return level >= ServiceLevel.DISCOVERED


def material_change(
    previous_materiality_digest: str | None,
    current_materiality_digest: str | None,
) -> bool:
    if not current_materiality_digest:
        return False
    return previous_materiality_digest != current_materiality_digest
