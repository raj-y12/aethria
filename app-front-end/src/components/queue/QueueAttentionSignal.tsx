import {
  attentionDriverQueueLabel,
  shouldRenderAttentionBadge,
  type QueueAttentionDriver,
} from '../../lib/queueAttentionDriver';

/**
 * Escalation-only mono line — no pills. Prefer QueueVerdictLine when the interrupt is the row's primary signal.
 */
export default function QueueAttentionSignal({
  driver,
  prominent = false,
}: {
  driver: QueueAttentionDriver;
  prominent?: boolean;
}) {
  const label = attentionDriverQueueLabel(driver);
  if (!shouldRenderAttentionBadge(driver) || !label) return null;

  return (
    <p
      className={`font-mono normal-case tracking-[0.04em] ${
        prominent ? 'text-[11px] text-escalation' : 'text-[10px] text-escalation/80'
      }`}
    >
      {label}
    </p>
  );
}
