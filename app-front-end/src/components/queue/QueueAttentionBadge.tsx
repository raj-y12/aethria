import { QUEUE_ANNOTATION_CLASS, VERDICT_CHIP_CLASS } from '../../design-system/verdictBadgeTokens';
import {
  attentionBadgeVariant,
  attentionDriverBadgeLabel,
  type QueueAttentionDriver,
  type QueueRowContext,
} from '../../lib/queueAttentionDriver';

export default function QueueAttentionBadge({
  driver,
  ctx,
  prominent: _prominent = false,
}: {
  driver: QueueAttentionDriver;
  ctx?: Pick<QueueRowContext, 'ageDays'>;
  prominent?: boolean;
}) {
  const label = attentionDriverBadgeLabel(driver, ctx);
  if (!label) return null;

  const variant = attentionBadgeVariant(driver);
  return (
    <span
      className={`${VERDICT_CHIP_CLASS} min-w-0 ${QUEUE_ANNOTATION_CLASS[variant]}`}
      aria-label={label}
    >
      {label}
    </span>
  );
}
