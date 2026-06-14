import type { CSSProperties } from 'react';
import type { VerdictBadgeConfig } from '../../lib/fundConfiguration';
import type { QueueAttentionDriver, QueueRowContext } from '../../lib/queueAttentionDriver';
import QueueAttentionBadge from './QueueAttentionBadge';

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

/** Escalated row marker — partner verdict colour bar + attention badge (reason on hover). */
export default function EscalationQueueMarker({
  ctx,
  driver,
}: {
  ctx: QueueRowContext;
  driver: QueueAttentionDriver;
}) {
  const recommendation = ctx.startup.partner?.recommendation ?? null;
  const reason = driver.detail?.trim();

  return (
    <div
      className="inline-flex max-w-full items-stretch gap-phi-1 rounded-none"
      title={reason || undefined}
      aria-label={reason ? `${driver.label}. ${reason}` : driver.label}
    >
      <span
        className="w-[5px] shrink-0 self-stretch"
        style={partnerVerdictBarStyle(recommendation, ctx.fundConfiguration?.verdictBadges)}
        aria-hidden
      />
      <QueueAttentionBadge driver={driver} ctx={{ ageDays: ctx.ageDays }} />
    </div>
  );
}
