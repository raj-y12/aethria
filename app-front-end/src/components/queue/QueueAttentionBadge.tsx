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
  prominent = false,
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
      className={`inline-flex shrink-0 items-center justify-center whitespace-nowrap rounded-none font-mono font-medium uppercase ${
        prominent ? 'py-[3px] px-phi-2 text-[10px] tracking-[0.13em]' : 'py-[2px] px-phi-2 text-[9px] tracking-[0.12em]'
      } ${QUEUE_ANNOTATION_CLASS[variant]}`}
      aria-label={label}
    >
      {label}
    </span>
  );
}
