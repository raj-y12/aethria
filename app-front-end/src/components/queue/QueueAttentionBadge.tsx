import { QUEUE_ANNOTATION_CLASS } from '../../design-system/verdictBadgeTokens';
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
  // Plain text mark, not a filled chip — annotations stay quieter than the verdict.
  return (
    <span
      className={`whitespace-nowrap font-mono text-[9px] font-semibold uppercase tracking-[0.1em] ${QUEUE_ANNOTATION_CLASS[variant]}`}
      aria-label={label}
    >
      {label}
    </span>
  );
}
