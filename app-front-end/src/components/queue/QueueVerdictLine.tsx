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
import { partnerRecommendationLabel } from '../../lib/recommendationSemantics';
import {
  attentionDriverBadgeLabel,
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
  const toneClass =
    tone === 'burgundy'
      ? prominent
        ? 'text-escalation'
        : 'text-escalation/80'
      : tone === 'muted'
        ? prominent
          ? 'text-oxford/65'
          : 'text-oxford/65'
        : prominent
          ? 'text-oxford/[0.72]'
          : 'text-oxford/65';
  return (
    <span className={`type-status ${toneClass}`}>{children}</span>
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
  const recommendationLabel = ctx.startup.human_resolution?.decision
    ? recommendation : partnerRecommendationLabel(ctx.startup.partner);
  const displayVariant = recommendationLabel === 'More diligence' ? 'escalation' : recommendation;
  const convictionPct = getQueueConvictionPct(ctx);
  const convictionLabel = convictionPct != null ? String(convictionPct) : null;
  const badgeVariant = queueDecisionBadgeVariant(decisionVariant, recommendation);

  const convictionEl =
    convictionLabel != null ? (
      <>
        <span className={prominent ? 'text-oxford/65' : 'text-oxford/[0.24]'} aria-hidden>
          ·
        </span>
        <span
          className={`type-data ${prominent ? 'text-oxford/75' : 'text-oxford/65'}`}
        >
          {convictionLabel}
        </span>
      </>
    ) : null;

  if (ctx.isEscalated && attentionDriver) {
    // Ambient escalated rows stay quiet mono text — a docket of eighty rows
    // must not become a wall of filled chips. The chip appears on selection.
    if (!prominent) {
      const quietLabel =
        attentionDriverBadgeLabel(attentionDriver, { ageDays: ctx.ageDays }) ?? 'Needs ruling';
      return (
        <div
          className="inline-flex flex-wrap items-center justify-end gap-x-phi-2 gap-y-0"
          aria-label={`Escalated${convictionLabel != null ? `, ${convictionLabel} conviction` : ''}`}
        >
          <QueueVerdictText tone="burgundy">{quietLabel}</QueueVerdictText>
          {convictionEl}
        </div>
      );
    }
    return (
      <div
        className="inline-flex flex-wrap items-center justify-end gap-x-phi-2 gap-y-0"
        aria-label={`Escalated${recommendationLabel ? `, partner recommends ${recommendationLabel.toLowerCase()}` : ''}${convictionLabel != null ? `, ${convictionLabel} conviction` : ''}`}
      >
        <EscalationQueueMarker ctx={ctx} driver={attentionDriver} />
        {recommendation && (
          <DecisionBadge
            variant={displayVariant ?? recommendation}
            label={recommendationLabel?.toUpperCase()}
            queue
            prominent={prominent}
          />
        )}
        {convictionEl}
      </div>
    );
  }

  if (recommendation) {
    return (
      <div
        className="inline-flex flex-wrap items-center justify-end gap-x-phi-2 gap-y-0"
        aria-label={`${recommendationLabel}${convictionLabel != null ? `, ${convictionLabel} conviction` : ''}`}
      >
        <DecisionBadge
          variant={displayVariant ?? recommendation}
          label={recommendationLabel?.toUpperCase()}
          queue
          prominent={prominent}
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
    <p className="type-status">—</p>
  );
}
