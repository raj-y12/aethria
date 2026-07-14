import { QUEUE_ANNOTATION_CLASS, VERDICT_CHIP_CLASS } from '../../design-system/verdictBadgeTokens';
import {
  attentionBadgeVariant,
  attentionDriverBadgeLabel,
  type QueueAttentionDriver,
  type QueueRowContext,
} from '../../lib/queueAttentionDriver';

/** Escalated row marker — attention label chip. */
export default function EscalationQueueMarker({
  ctx,
  driver,
}: {
  ctx: QueueRowContext;
  driver: QueueAttentionDriver;
}) {
  const reason = driver.detail?.trim();
  const label = attentionDriverBadgeLabel(driver, { ageDays: ctx.ageDays });
  if (!label) return null;

  const variant = attentionBadgeVariant(driver);

  return (
    <div
      className="inline-flex max-w-full items-stretch rounded-none"
      title={reason || undefined}
      aria-label={reason ? `${driver.label}. ${reason}` : driver.label}
    >
      <span className={`${VERDICT_CHIP_CLASS} min-w-0 ${QUEUE_ANNOTATION_CLASS[variant]}`}>{label}</span>
    </div>
  );
}
