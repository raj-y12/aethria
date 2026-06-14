/**
 * Queue verdict — filled decision badge + conviction integer.
 * The verdict is the one per-row signal that earns colour: a soft-palette filled
 * chip (DecisionBadge) makes INVEST / PASS / MONITOR scannable at a glance.
 * Pipeline/escalation interrupt states stay as calm text.
 */
import type { ReactNode } from 'react';
import DecisionBadge from '../DecisionBadge';
import EscalationQueueMarker from './EscalationQueueMarker';
import type { DecisionBadgeVariant } from '../../lib/decisionBadgeVariant';
import {
  getQueueConvictionPct,
  getVisibleRecommendation,
  type QueueAttentionDriver,
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
          : 'text-oxford/[0.38]'
        : prominent
          ? 'text-oxford/[0.72]'
          : 'text-oxford/50';
  return (
    <span className={`font-mono uppercase tracking-[0.08em] ${size} ${toneClass}`}>{children}</span>
  );
}

export default function QueueVerdictLine({
  ctx,
  decisionVariant,
  prominent = false,
  attentionDriver,
}: {
  ctx: QueueRowContext;
  decisionVariant: DecisionBadgeVariant;
  prominent?: boolean;
  badges?: unknown;
  attentionDriver?: QueueAttentionDriver;
}) {
  const recommendation = getVisibleRecommendation(ctx.startup);
  const convictionPct = getQueueConvictionPct(ctx);
  const convictionLabel = convictionPct != null ? String(convictionPct) : null;
  const badgeVariant = queueDecisionBadgeVariant(decisionVariant, recommendation);

  const convictionEl =
    convictionLabel != null ? (
      <>
        <span className={prominent ? 'text-oxford/30' : 'text-oxford/[0.24]'} aria-hidden>
          ·
        </span>
        <span
          className={`font-mono tabular-nums ${
            prominent ? 'text-[12px] font-semibold text-oxford/75' : 'text-[11px] font-medium text-oxford/55'
          }`}
        >
          {convictionLabel}
        </span>
      </>
    ) : null;

  if (ctx.isEscalated && attentionDriver) {
    return (
      <div
        className="inline-flex flex-wrap items-center justify-end gap-x-phi-2 gap-y-0"
        aria-label={`Escalated${convictionLabel != null ? `, ${convictionLabel} conviction` : ''}`}
      >
        <EscalationQueueMarker ctx={ctx} driver={attentionDriver} />
        {convictionEl}
      </div>
    );
  }

  if (recommendation) {
    return (
      <div
        className="inline-flex flex-wrap items-center justify-end gap-x-phi-2 gap-y-0"
        aria-label={`${recommendation}${convictionLabel != null ? `, ${convictionLabel} conviction` : ''}`}
      >
        <DecisionBadge
          variant={recommendation}
          queue
          prominent={prominent}
          badges={ctx.fundConfiguration?.verdictBadges}
        />
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
