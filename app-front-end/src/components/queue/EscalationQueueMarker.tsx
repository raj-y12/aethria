import type { CSSProperties } from 'react';
import { QUEUE_ANNOTATION_CLASS, VERDICT_CHIP_CLASS } from '../../design-system/verdictBadgeTokens';
import type { VerdictBadgeConfig } from '../../lib/fundConfiguration';
import {
  attentionBadgeVariant,
  attentionDriverBadgeLabel,
  type QueueAttentionDriver,
  type QueueRowContext,
} from '../../lib/queueAttentionDriver';

const PARTNER_VERDICT_BAR_FALLBACK: Record<'INVEST' | 'PASS' | 'MONITOR', string> = {
  INVEST: '#bfe3cc',
  PASS: '#eabfb7',
  MONITOR: '#e5d39f',
};

function partnerVerdictBarStyle(
  recommendation: 'INVEST' | 'PASS' | 'MONITOR' | null | undefined,
  badges?: VerdictBadgeConfig[]
): CSSProperties {
  if (!recommendation) {
    return { backgroundColor: 'color-mix(in srgb, var(--color-oxford) 16%, transparent)' };
  }
  const custom = badges?.find((badge) => badge.id === recommendation)?.backgroundColor;
  return { backgroundColor: custom ?? PARTNER_VERDICT_BAR_FALLBACK[recommendation] };
}

/** Escalated row marker — partner verdict bar fused with attention label. */
export default function EscalationQueueMarker({
  ctx,
  driver,
}: {
  ctx: QueueRowContext;
  driver: QueueAttentionDriver;
}) {
  const recommendation = ctx.startup.partner?.recommendation ?? null;
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
      <span
        className="w-[7px] shrink-0 self-stretch"
        style={partnerVerdictBarStyle(recommendation, ctx.fundConfiguration?.verdictBadges)}
        aria-hidden
      />
      <span className={`${VERDICT_CHIP_CLASS} min-w-0 ${QUEUE_ANNOTATION_CLASS[variant]}`}>{label}</span>
    </div>
  );
}
