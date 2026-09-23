/**
 * Shown instead of the full memo when a startup is held back by the
 * periodic pipeline's Scout confidence gate. It offers a manual review and a
 * way to back out. Partner decisions must come from canonical evidence.
 */
import { useState } from 'react';
import type { Startup } from '../types/startup';
import { SCOUT_THESIS_FIT_CATEGORIES, type TriageGateStatus } from '../lib/triageGate';
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
  const stage = 'review';
  const actionLabel = 'Review it anyway';
  const kicker = `Matched ${Math.round(status.confidence * SCOUT_THESIS_FIT_CATEGORIES)} of ${SCOUT_THESIS_FIT_CATEGORIES} mandate categories (sector, stage, geography) -- below the bar the pipeline reviews at automatically.`;

  if (dismissed) return null;

  return (
    <div className="memoEmpty">
      <div className="memoEmptyInner flex flex-col items-center gap-phi-4">
        <p className={productText.mutedLabel}>Held by triage funnel</p>
        <h3 className="font-sans text-xl font-semibold leading-tight tracking-[-0.03em] text-oxford sm:text-2xl">
          {startup.scout.name}
        </h3>
        <p className={productText.body}>{kicker}</p>
        {error ? <p className="type-body-sm text-red-700">{error}</p> : null}
        <div className="mt-phi-2 flex flex-wrap items-center justify-center gap-phi-3">
          <button
            type="button"
            disabled={pending}
            className="btn-aethria-solid disabled:cursor-not-allowed disabled:opacity-40"
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
            className="type-action inline-flex h-9 items-center justify-center px-phi-3 text-oxford/65 transition-colors hover:text-oxford disabled:cursor-not-allowed disabled:opacity-40 focus:outline-none focus-visible:ring-2 focus-visible:ring-oxford/30"
            onClick={() => {
              setDismissed(true);
              onClose?.();
            }}
          >
            <span className="border-b border-oxford/10 pb-0.5 transition-colors hover:border-oxford/40">
              Not now
            </span>
          </button>
        </div>
      </div>
    </div>
  );
}
