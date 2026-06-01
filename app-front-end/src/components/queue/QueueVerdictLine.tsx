/**
 * Queue verdict — typography only (no filled pills).
 * One calm line: recommendation + conviction, pipeline state, or escalation interrupt.
 */
import type { ReactNode } from 'react';
import { DECISION_LABELS } from '../../design-system/semantics';
import type { DecisionBadgeVariant } from '../../lib/decisionBadgeVariant';
import {
  getQueueConvictionPct,
  getVisibleRecommendation,
  type QueueRowContext,
} from '../../lib/queueAttentionDriver';

function queueDecisionBadgeVariant(
  decisionVariant: DecisionBadgeVariant,
  recommendation: ReturnType<typeof getVisibleRecommendation>
): DecisionBadgeVariant {
  if (recommendation === 'INVEST' || recommendation === 'PASS' || recommendation === 'MONITOR') {
    return recommendation;
  }
  return decisionVariant;
}

function QueueVerdictText({
  children,
  prominent = false,
  tone = 'default',
}: {
  children: ReactNode;
  prominent?: boolean;
  tone?: 'default' | 'burgundy' | 'muted';
}) {
  const size = prominent ? 'text-[11px]' : 'text-[10px]';
  const toneClass =
    tone === 'burgundy'
      ? prominent
        ? 'text-escalation'
        : 'text-escalation/80'
      : tone === 'muted'
        ? prominent
          ? 'text-oxford/45'
          : 'text-oxford/38'
        : prominent
          ? 'text-oxford/72'
          : 'text-oxford/50';
  return (
    <span className={`font-mono uppercase tracking-[0.08em] ${size} ${toneClass}`}>{children}</span>
  );
}

export default function QueueVerdictLine({
  ctx,
  decisionVariant,
  prominent = false,
}: {
  ctx: QueueRowContext;
  decisionVariant: DecisionBadgeVariant;
  prominent?: boolean;
  badges?: unknown;
}) {
  const recommendation = getVisibleRecommendation(ctx.startup);
  const convictionPct = getQueueConvictionPct(ctx);
  const badgeVariant = queueDecisionBadgeVariant(decisionVariant, recommendation);

  // Conviction is a single bold integer — a clean right-anchor number, no "%".
  const convictionEl =
    convictionPct != null ? (
      <>
        <span className={prominent ? 'text-oxford/30' : 'text-oxford/24'} aria-hidden>
          ·
        </span>
        <span
          className={`font-mono tabular-nums ${
            prominent ? 'text-[12px] font-semibold text-oxford/75' : 'text-[11px] font-medium text-oxford/55'
          }`}
        >
          {convictionPct}
        </span>
      </>
    ) : null;

  if (recommendation) {
    const label = (DECISION_LABELS[recommendation] ?? recommendation).toUpperCase();
    return (
      <div
        className="inline-flex flex-wrap items-baseline justify-end gap-x-phi-2 gap-y-0"
        aria-label={`${recommendation}${convictionPct != null ? `, ${convictionPct} conviction` : ''}`}
      >
        <QueueVerdictText prominent={prominent}>{label}</QueueVerdictText>
        {convictionEl}
      </div>
    );
  }

  if (badgeVariant === 'escalation') {
    return (
      <div className="inline-flex items-baseline justify-end">
        <QueueVerdictText prominent={prominent} tone="burgundy">
          Needs ruling
        </QueueVerdictText>
      </div>
    );
  }

  if (badgeVariant === 'awaiting') {
    return (
      <div className="inline-flex items-baseline justify-end">
        <QueueVerdictText prominent={prominent} tone="muted">
          Awaiting review
        </QueueVerdictText>
      </div>
    );
  }

  if (badgeVariant === 'undecided') {
    return (
      <div className="inline-flex items-baseline justify-end">
        <QueueVerdictText prominent={prominent} tone="muted">
          Pending decision
        </QueueVerdictText>
      </div>
    );
  }

  return (
    <p className={`font-mono uppercase ${prominent ? 'text-[11px]' : 'text-[10px]'} text-oxford/35`}>—</p>
  );
}
