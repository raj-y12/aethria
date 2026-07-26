import { useEffect, useMemo, useRef, useState, type KeyboardEvent, type PointerEvent } from 'react';
import {
  applyDecisionThresholds,
  commitScoreInput,
  formatReviewerAvg,
  getDecisionThresholdBoundaries,
  validateDecisionThresholds,
  type DecisionThresholdBoundaries,
} from '../lib/decisionThresholds';
import type { FundConfiguration } from '../lib/fundConfiguration';

const labelCls = 'type-label-section text-xs text-oxford/70';
const inputCls =
  'type-data w-full max-w-[5.5rem] rounded-none border-0 border-b border-oxford/[0.12] bg-transparent px-0 py-phi-2 text-oxford outline-none transition-colors focus:border-oxford/45';

const bandColors = {
  pass: '#d6a39d',
  monitor: '#d7bf72',
  invest: '#8dc2a1',
};

export function scoreFromPointer(clientX: number, left: number, width: number): number {
  if (width <= 0) return 0;
  const ratio = (clientX - left) / width;
  return Math.round(Math.min(1, Math.max(0, ratio)) * 100);
}

type BoundaryKey = keyof DecisionThresholdBoundaries;

function ThresholdHandle({
  boundaryKey,
  label,
  value,
  min,
  max,
  variant,
  barRef,
  onChange,
}: {
  boundaryKey: BoundaryKey;
  label: string;
  value: number;
  min: number;
  max: number;
  variant: 'tick' | 'divider';
  barRef: React.RefObject<HTMLDivElement | null>;
  onChange: (patch: Partial<DecisionThresholdBoundaries>) => void;
}) {
  const setFromPointer = (event: PointerEvent<HTMLButtonElement>) => {
    const rect = barRef.current?.getBoundingClientRect();
    if (!rect) return;
    onChange({ [boundaryKey]: scoreFromPointer(event.clientX, rect.left, rect.width) });
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLButtonElement>) => {
    let next: number | null = null;
    if (event.key === 'ArrowLeft' || event.key === 'ArrowDown') next = value - 1;
    if (event.key === 'ArrowRight' || event.key === 'ArrowUp') next = value + 1;
    if (event.key === 'Home') next = min;
    if (event.key === 'End') next = max;
    if (next == null) return;
    event.preventDefault();
    onChange({ [boundaryKey]: Math.min(max, Math.max(min, next)) });
  };

  return (
    <button
      type="button"
      role="slider"
      aria-label={label}
      aria-valuemin={min}
      aria-valuemax={max}
      aria-valuenow={value}
      aria-valuetext={`${value}, reviewer average ${formatReviewerAvg(value)}`}
      onKeyDown={handleKeyDown}
      onPointerDown={(event) => {
        event.currentTarget.setPointerCapture(event.pointerId);
        setFromPointer(event);
      }}
      onPointerMove={(event) => {
        if (!event.currentTarget.hasPointerCapture(event.pointerId)) return;
        setFromPointer(event);
      }}
      className="group absolute top-1/2 z-[2] flex h-11 w-11 -translate-x-1/2 -translate-y-1/2 touch-none items-center justify-center focus:outline-none focus-visible:ring-2 focus-visible:ring-oxford/55"
      style={{ left: `${value}%` }}
    >
      <span
        className={`pointer-events-none absolute -top-phi-4 type-data ${variant === 'divider' ? 'text-oxford' : 'text-oxford/70'}`}
        aria-hidden
      >
        {value}
      </span>
      {variant === 'divider' ? (
        <>
          <span className="absolute inset-y-1 w-[2px] bg-oxford" aria-hidden />
          <span className="relative h-3 w-3 bg-oxford ring-2 ring-paper transition-transform group-hover:scale-110 group-focus-visible:ring-2 group-focus-visible:ring-oxford/45" aria-hidden />
        </>
      ) : (
        <span className="flex h-5 w-3 items-end justify-center border-b-2 border-oxford/70" aria-hidden>
          <span className="h-2.5 w-px bg-oxford/70" />
        </span>
      )}
    </button>
  );
}

function ThresholdBar({
  boundaries,
  onChange,
}: {
  boundaries: DecisionThresholdBoundaries;
  onChange: (patch: Partial<DecisionThresholdBoundaries>) => void;
}) {
  const barRef = useRef<HTMLDivElement>(null);
  const passMax = boundaries.passMonitorBoundary - 1;
  const monitorMax = boundaries.monitorInvestBoundary - 1;

  return (
    <div className="pt-phi-6">
      <div ref={barRef} className="relative h-11 w-full">
        <div className="flex h-full w-full overflow-hidden border border-oxford/[0.1]">
          <div
            className="type-status flex items-center justify-center text-xs text-oxford/70"
            style={{ width: `${boundaries.passMonitorBoundary}%`, backgroundColor: bandColors.pass }}
          >
            Pass
          </div>
          <div
            className="type-status flex items-center justify-center text-xs text-oxford/70"
            style={{
              width: `${boundaries.monitorInvestBoundary - boundaries.passMonitorBoundary}%`,
              backgroundColor: bandColors.monitor,
            }}
          >
            Monitor
          </div>
          <div
            className="type-status flex items-center justify-center text-xs text-oxford/70"
            style={{ width: `${100 - boundaries.monitorInvestBoundary}%`, backgroundColor: bandColors.invest }}
          >
            Invest
          </div>
        </div>
        <ThresholdHandle
          boundaryKey="autoPassCeiling"
          label="Auto-pass ceiling"
          value={boundaries.autoPassCeiling}
          min={0}
          max={Math.max(0, boundaries.passMonitorBoundary - 1)}
          variant="tick"
          barRef={barRef}
          onChange={onChange}
        />
        <ThresholdHandle
          boundaryKey="passMonitorBoundary"
          label="Monitor starts"
          value={boundaries.passMonitorBoundary}
          min={2}
          max={Math.max(2, boundaries.monitorInvestBoundary - 1)}
          variant="divider"
          barRef={barRef}
          onChange={onChange}
        />
        <ThresholdHandle
          boundaryKey="monitorInvestBoundary"
          label="Invest starts"
          value={boundaries.monitorInvestBoundary}
          min={Math.min(100, boundaries.passMonitorBoundary + 1)}
          max={100}
          variant="divider"
          barRef={barRef}
          onChange={onChange}
        />
      </div>
      <p className="type-data mt-phi-2 text-oxford/70">
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

  useEffect(() => {
    setText(String(value));
  }, [value]);

  const handleChange = (raw: string) => {
    const nextText = raw.replace(/[^\d]/g, '');
    setText(nextText);
    if (nextText === '') return;
    const parsed = Number.parseInt(nextText, 10);
    if (!Number.isFinite(parsed) || parsed < min || parsed > max) return;
    if (parsed !== value) onCommit(parsed);
  };

  return (
    <div className="flex min-w-0 flex-col gap-phi-2">
      <label htmlFor={id} className={labelCls}>{label}</label>
      <div className="flex flex-wrap items-baseline gap-phi-3">
        <input
          id={id}
          type="number"
          inputMode="numeric"
          min={min}
          max={max}
          step={1}
          value={text}
          onChange={(event) => handleChange(event.target.value)}
          onBlur={() => {
            const next = commitScoreInput(text, min, max, value);
            if (next !== value) onCommit(next);
            setText(String(next));
          }}
          className={inputCls}
          aria-describedby={suffix ? `${id}-suffix` : undefined}
        />
        {suffix && (
          <span id={`${id}-suffix`} className="type-meta text-xs text-oxford/70">{suffix}</span>
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

  useEffect(() => {
    setText(String(value));
  }, [value]);

  return (
    <div className="flex min-w-0 flex-col gap-phi-2">
      <label htmlFor={id} className={labelCls}>{label}</label>
      <input
        id={id}
        type="text"
        inputMode="decimal"
        value={text}
        onChange={(event) => {
          const nextText = event.target.value.replace(/[^\d.]/g, '');
          setText(nextText);
          if (nextText === '' || nextText === '.') return;
          const parsed = Number.parseFloat(nextText);
          if (!Number.isFinite(parsed) || parsed < min || parsed > max) return;
          if (parsed !== value) onCommit(parsed);
        }}
        onBlur={() => {
          const parsed = Number.parseFloat(text);
          const next = Number.isFinite(parsed) ? Math.min(max, Math.max(min, parsed)) : value;
          if (next !== value) onCommit(next);
          setText(String(next));
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

      <ThresholdBar boundaries={boundaries} onChange={applyBounds} />

      <div>
        <p className="type-note text-oxford/70">
          Drag a marker, use arrow keys, or enter an exact score.
        </p>
        <div className="mt-phi-4 grid gap-phi-5 sm:grid-cols-3">
          <ScoreInput
            id="monitor-start"
            label="Monitor starts at"
            value={boundaries.passMonitorBoundary}
            min={2}
            max={boundaries.monitorInvestBoundary - 1}
            onCommit={(value) => applyBounds({ passMonitorBoundary: value })}
          />
          <ScoreInput
            id="invest-start"
            label="Invest starts at"
            value={boundaries.monitorInvestBoundary}
            min={boundaries.passMonitorBoundary + 1}
            max={100}
            onCommit={(value) => applyBounds({ monitorInvestBoundary: value })}
          />
          <ScoreInput
            id="auto-pass-below"
            label="Auto-pass below"
            value={boundaries.autoPassCeiling}
            min={0}
            max={boundaries.passMonitorBoundary - 1}
            onCommit={(value) => applyBounds({ autoPassCeiling: value })}
          />
        </div>
      </div>

      <div className="grid gap-phi-7 pt-phi-5 sm:grid-cols-2">
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
          label="Min scout confidence"
          value={draft.thresholds.confidenceFloor}
          min={0}
          max={1}
          onCommit={(value) => updateThreshold('confidenceFloor', value)}
        />
      </div>
    </div>
  );
}
