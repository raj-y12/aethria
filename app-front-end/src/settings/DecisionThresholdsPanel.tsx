import { useEffect, useMemo, useState } from 'react';
import {
  applyDecisionThresholds,
  commitScoreInput,
  formatReviewerAvg,
  getDecisionThresholdBoundaries,
  validateDecisionThresholds,
  type DecisionThresholdBoundaries,
} from '../lib/decisionThresholds';
import type { FundConfiguration } from '../lib/fundConfiguration';
import { DEFAULT_VERDICT_BADGES } from '../lib/fundConfiguration';

const labelCls = 'type-label-section text-oxford/45';
const inputCls =
  'w-full max-w-[5.5rem] rounded-none border-0 border-b border-oxford/[0.12] bg-transparent px-0 py-phi-2 type-body-sm font-mono tabular-nums text-oxford outline-none transition-colors focus:border-oxford/45';

const bandColors = {
  pass: DEFAULT_VERDICT_BADGES.find((b) => b.id === 'PASS')?.backgroundColor ?? '#eabfb7',
  monitor: DEFAULT_VERDICT_BADGES.find((b) => b.id === 'MONITOR')?.backgroundColor ?? '#e5d39f',
  invest: DEFAULT_VERDICT_BADGES.find((b) => b.id === 'INVEST')?.backgroundColor ?? '#bfe3cc',
};

function ThresholdBar({ boundaries }: { boundaries: DecisionThresholdBoundaries }) {
  const passMax = boundaries.passMonitorBoundary - 1;
  const monitorMax = boundaries.monitorInvestBoundary - 1;

  return (
    <div>
      <div className="flex h-9 w-full overflow-hidden border border-oxford/[0.1]">
        <div
          className="flex items-center justify-center type-meta uppercase tracking-badge text-oxford/70"
          style={{ width: `${boundaries.passMonitorBoundary}%`, backgroundColor: bandColors.pass }}
        >
          Pass
        </div>
        <div
          className="flex items-center justify-center type-meta uppercase tracking-badge text-oxford/70"
          style={{
            width: `${boundaries.monitorInvestBoundary - boundaries.passMonitorBoundary}%`,
            backgroundColor: bandColors.monitor,
          }}
        >
          Monitor
        </div>
        <div
          className="flex items-center justify-center type-meta uppercase tracking-badge text-oxford/70"
          style={{ width: `${100 - boundaries.monitorInvestBoundary}%`, backgroundColor: bandColors.invest }}
        >
          Invest
        </div>
      </div>
      <p className="mt-phi-2 font-mono text-[11px] tabular-nums text-oxford/42">
        0–{passMax} · {boundaries.passMonitorBoundary}–{monitorMax} · {boundaries.monitorInvestBoundary}–100
      </p>
    </div>
  );
}

function ScoreInput({
  id,
  label,
  suffix,
  value,
  min,
  max,
  onCommit,
}: {
  id: string;
  label: string;
  suffix?: string;
  value: number;
  min: number;
  max: number;
  onCommit: (value: number) => void;
}) {
  const [text, setText] = useState(String(value));
  const [focused, setFocused] = useState(false);

  useEffect(() => {
    if (!focused) setText(String(value));
  }, [value, focused]);

  return (
    <div className="flex min-w-0 flex-col gap-phi-2">
      <label htmlFor={id} className={labelCls}>{label}</label>
      <div className="flex flex-wrap items-baseline gap-phi-3">
        <input
          id={id}
          type="text"
          inputMode="numeric"
          pattern="[0-9]*"
          value={text}
          onFocus={() => setFocused(true)}
          onChange={(event) => setText(event.target.value.replace(/[^\d]/g, ''))}
          onBlur={() => {
            setFocused(false);
            const next = commitScoreInput(text, min, max, value);
            onCommit(next);
            setText(String(next));
          }}
          onKeyDown={(event) => {
            if (event.key === 'Enter') (event.target as HTMLInputElement).blur();
          }}
          className={inputCls}
          aria-describedby={suffix ? `${id}-suffix` : undefined}
        />
        {suffix && (
          <span id={`${id}-suffix`} className="type-meta text-oxford/40">{suffix}</span>
        )}
      </div>
    </div>
  );
}

function DecimalInput({
  id,
  label,
  value,
  min,
  max,
  onCommit,
}: {
  id: string;
  label: string;
  value: number;
  min: number;
  max: number;
  onCommit: (value: number) => void;
}) {
  const [text, setText] = useState(String(value));
  const [focused, setFocused] = useState(false);

  useEffect(() => {
    if (!focused) setText(String(value));
  }, [value, focused]);

  return (
    <div className="flex min-w-0 flex-col gap-phi-2">
      <label htmlFor={id} className={labelCls}>{label}</label>
      <input
        id={id}
        type="text"
        inputMode="decimal"
        value={text}
        onFocus={() => setFocused(true)}
        onChange={(event) => setText(event.target.value.replace(/[^\d.]/g, ''))}
        onBlur={() => {
          setFocused(false);
          const parsed = Number.parseFloat(text);
          const next = Number.isFinite(parsed) ? Math.min(max, Math.max(min, parsed)) : value;
          onCommit(next);
          setText(String(next));
        }}
        onKeyDown={(event) => {
          if (event.key === 'Enter') (event.target as HTMLInputElement).blur();
        }}
        className={inputCls}
      />
    </div>
  );
}

export default function DecisionThresholdsPanel({
  draft,
  updateDraft,
  updateThreshold,
}: {
  draft: FundConfiguration;
  updateDraft: (updater: (current: FundConfiguration) => FundConfiguration) => void;
  updateThreshold: <K extends keyof FundConfiguration['thresholds']>(
    key: K,
    value: FundConfiguration['thresholds'][K],
  ) => void;
}) {
  const boundaries = useMemo(() => getDecisionThresholdBoundaries(draft), [draft]);
  const validation = useMemo(() => validateDecisionThresholds(draft), [draft]);

  const applyBounds = (patch: Partial<DecisionThresholdBoundaries>) => {
    updateDraft((current) => applyDecisionThresholds(current, patch));
  };

  return (
    <div className="flex flex-col gap-phi-6">
      {!validation.valid && (
        <div className="border border-escalation/25 bg-escalation/[0.035] px-phi-4 py-phi-3">
          {validation.errors.map((error) => (
            <p key={error} className="type-body-sm text-escalation/75">{error}</p>
          ))}
        </div>
      )}

      <ThresholdBar boundaries={boundaries} />

      <div className="grid gap-phi-5 sm:grid-cols-3">
        <ScoreInput
          id="threshold-monitor-start"
          label="Monitor starts at"
          suffix={`avg ${formatReviewerAvg(boundaries.passMonitorBoundary)}`}
          value={boundaries.passMonitorBoundary}
          min={2}
          max={99}
          onCommit={(value) => applyBounds({ passMonitorBoundary: value })}
        />
        <ScoreInput
          id="threshold-invest-start"
          label="Invest starts at"
          suffix={`avg ${formatReviewerAvg(boundaries.monitorInvestBoundary)}`}
          value={boundaries.monitorInvestBoundary}
          min={boundaries.passMonitorBoundary + 1}
          max={100}
          onCommit={(value) => applyBounds({ monitorInvestBoundary: value })}
        />
        <ScoreInput
          id="threshold-auto-pass"
          label="Auto-pass below"
          suffix={`avg ${formatReviewerAvg(boundaries.autoPassCeiling)}`}
          value={boundaries.autoPassCeiling}
          min={0}
          max={Math.max(0, boundaries.passMonitorBoundary - 1)}
          onCommit={(value) => applyBounds({ autoPassCeiling: value })}
        />
      </div>

      <div className="grid gap-phi-5 border-t border-oxford/[0.055] pt-phi-5 sm:grid-cols-2">
        <ScoreInput
          id="stale-after"
          label="Stale after (hours)"
          value={draft.thresholds.staleAfterHours}
          min={1}
          max={720}
          onCommit={(value) => updateThreshold('staleAfterHours', value)}
        />
        <DecimalInput
          id="confidence-floor"
          label="Scout confidence min"
          value={draft.thresholds.confidenceFloor}
          min={0}
          max={1}
          onCommit={(value) => updateThreshold('confidenceFloor', value)}
        />
      </div>
    </div>
  );
}
