/**
 * Shown instead of the full memo when a startup is held back by the
 * periodic pipeline's triage funnel gates (confidence_threshold /
 * decision_threshold) -- see getTriageGateStatus. Just the company name and
 * why it's gated, with a manual "review it anyway" / "decide it anyway"
 * action and a way to back out. No memo content is generated or shown.
 */
import { useState } from 'react';
import type { Startup } from '../types/startup';
import type { TriageGateStatus } from '../lib/triageGate';
import { useTriageOverride } from '../hooks/useTriageOverride';
import { productText } from '../design-system/productSystem';

interface TriageGateCardProps {
  startup: Startup;
  status: Extract<TriageGateStatus, { gated: true }>;
  onClose?: () => void;
  /** Called once the override succeeds, so the caller can re-check gate status and mount the memo. */
  onOverridden?: () => void;
}

export default function TriageGateCard({ startup, status, onClose, onOverridden }: TriageGateCardProps) {
  const { run, pendingId, error } = useTriageOverride();
  const [dismissed, setDismissed] = useState(false);
  const pending = pendingId === startup.id;
  const stage = status.reason === 'not_reviewed' ? 'review' : 'decide';
  const actionLabel = stage === 'review' ? 'Review it' : 'Decide it anyway';
  const kicker =
    status.reason === 'not_reviewed'
      ? `Scout confidence ${Math.round(status.confidence * 100)}% is below the ${Math.round(status.threshold * 100)}% review bar -- not yet reviewed.`
      : `Reviewer score ${Math.round(status.overallScore * 10)}% is below the ${Math.round(status.threshold * 100)}% decision bar -- reviewed, not decided.`;

  if (dismissed) return null;

  return (
    <article className="flex w-full flex-col items-start gap-phi-4 border border-solid border-oxford/10 bg-paper px-phi-6 py-phi-7 text-left sm:px-phi-7">
      <p className={`${productText.mutedLabel} max-w-xs`}>Held by triage funnel</p>
      <h3 className="pc-font-display text-xl font-medium leading-tight tracking-[-0.02em] text-oxford sm:text-2xl">
        {startup.scout.name}
      </h3>
      <p className={`${productText.body} max-w-[28rem]`}>{kicker}</p>
      {error ? <p className="type-body-sm text-red-700">{error}</p> : null}
      <div className="mt-phi-2 flex w-full flex-wrap items-center gap-phi-3">
        <button
          type="button"
          disabled={pending}
          className="type-action border border-solid border-oxford/12 bg-oxford px-phi-5 py-2.5 text-paper transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-30"
          onClick={() => {
            void run(startup.id, stage).then((ok) => {
              if (ok) onOverridden?.();
            });
          }}
        >
          {pending ? 'Working…' : actionLabel}
        </button>
        <button
          type="button"
          disabled={pending}
          className="type-action border border-solid border-oxford/12 bg-transparent px-phi-5 py-2.5 text-oxford transition-colors hover:bg-oxford/[0.035] disabled:cursor-not-allowed disabled:opacity-30"
          onClick={() => {
            setDismissed(true);
            onClose?.();
          }}
        >
          Not now
        </button>
      </div>
    </article>
  );
}
