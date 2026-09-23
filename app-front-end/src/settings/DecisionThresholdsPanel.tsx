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
import { SCORE_BAND_DOT_COLORS } from '../design-system/verdictScoreTokens';

const labelCls = 'type-label-section text-xs text-oxford/70';
const inputCls =
  'type-data w-full max-w-[5.5rem] rounded-none border-0 border-b border-oxford/[0.12] bg-transparent px-0 py-phi-2 text-oxford outline-none transition-colors focus:border-oxford/45';

const bandColors = SCORE_BAND_DOT_COLORS;

/** Clip a full-width layer down to [from, to] on the 0–100 score axis. */
function bandClip(from: number, to: number): React.CSSProperties {
  return { '--band-left': `${from}%`, '--band-right': `${100 - to}%` } as React.CSSProperties;
}

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
  onDrag,
}: {
  boundaryKey: BoundaryKey;
  label: string;
  value: number;
  min: number;
  max: number;
  variant: 'tick' | 'divider';
  barRef: React.RefObject<HTMLDivElement | null>;
  onChange: (patch: Partial<DecisionThresholdBoundaries>) => void;
  onDrag: (delta: number | null) => void;
}) {
  const setFromPointer = (event: PointerEvent<HTMLButtonElement>) => {
    const rect = barRef.current?.getBoundingClientRect();
    if (!rect) return;
    const next = scoreFromPointer(event.clientX, rect.left, rect.width);
    onDrag(next - value);
    onChange({ [boundaryKey]: next });
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
        onDrag(0);
        setFromPointer(event);
      }}
      onPointerMove={(event) => {
        if (!event.currentTarget.hasPointerCapture(event.pointerId)) return;
        setFromPointer(event);
      }}
      onLostPointerCapture={() => onDrag(null)}
      className="group absolute top-1/2 z-[2] flex h-full w-11 -translate-x-1/2 -translate-y-1/2 touch-none items-center justify-center focus:outline-none focus-visible:ring-2 focus-visible:ring-oxford/55"
      style={{ left: `${value}%` }}
    >
      {/* Outside the frame so the divider rule never crosses the digits.
          Dividers ride above, the auto-pass tick below — they can sit 1 apart. */}
      <span
        className={`pointer-events-none absolute type-data leading-none ${
          variant === 'divider' ? '-top-5 text-oxford' : '-bottom-5 text-oxford/70'
        }`}
        aria-hidden
      >
        {value}
      </span>
      {variant === 'divider' ? (
        <>
          <span className="absolute inset-y-1 w-[2px] bg-oxford" aria-hidden />
          <span className="relative h-3 w-3 bg-oxford ring-2 ring-paper transition-transform duration-150 ease-out group-hover:scale-110 group-active:scale-[1.35] group-focus-visible:ring-2 group-focus-visible:ring-oxford/45" aria-hidden />
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
  compact,
}: {
  boundaries: DecisionThresholdBoundaries;
  onChange: (patch: Partial<DecisionThresholdBoundaries>) => void;
  compact: boolean;
}) {
  const barRef = useRef<HTMLDivElement>(null);
  const passMax = boundaries.passMonitorBoundary - 1;
  const monitorMax = boundaries.monitorInvestBoundary - 1;
  // null = not dragging. While dragging, the last pointer delta leans the bands
  // in the direction of travel and relaxes to 0 the moment you hold still —
  // pointer events alone can't detect "holding still", so an idle timer
  // restarted on every move drives the relax.
  const [drag, setDrag] = useState<number | null>(null);
  const idleTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const clearIdleTimer = () => {
    if (idleTimerRef.current != null) {
      clearTimeout(idleTimerRef.current);
      idleTimerRef.current = null;
    }
  };
  useEffect(() => clearIdleTimer, []);
  const onDrag = (delta: number | null) => {
    clearIdleTimer();
    if (delta == null) {
      setDrag(null);
      return;
    }
    setDrag(Math.max(-10, Math.min(10, delta * 2.5)));
    idleTimerRef.current = setTimeout(() => setDrag(0), 120);
  };

  return (
    <div className="pt-6">
      <div ref={barRef} className={`relative w-full border-y border-oxford/[0.08] ${compact ? 'h-10' : 'h-24 lg:h-28'}`}>
        <div
          data-testid="threshold-dot-grid"
          data-dragging={drag != null}
          className="threshold-matrix pointer-events-none overflow-hidden"
          style={{ '--lean': `${drag ?? 0}deg` } as React.CSSProperties}
          aria-hidden
        >
          <div
            className="threshold-band"
            style={{ ...bandClip(0, boundaries.passMonitorBoundary), backgroundColor: bandColors.pass }}
          />
          <div
            className="threshold-band"
            style={{
              ...bandClip(boundaries.passMonitorBoundary, boundaries.monitorInvestBoundary),
              backgroundColor: bandColors.monitor,
            }}
          />
          <div
            className="threshold-band"
            style={{ ...bandClip(boundaries.monitorInvestBoundary, 100), backgroundColor: bandColors.invest }}
          />
          <div
            className="threshold-band threshold-autopass"
            style={bandClip(0, boundaries.autoPassCeiling)}
          />
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
          onDrag={onDrag}
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
          onDrag={onDrag}
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
          onDrag={onDrag}
        />
      </div>
      <div className={`${compact ? 'mt-6' : 'mt-7'} flex flex-wrap items-center gap-x-phi-5 gap-y-phi-2 type-data text-oxford/70`}>
        <span className="inline-flex items-center gap-phi-2">
          <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: bandColors.pass }} aria-hidden />
          Pass 0–{passMax}
        </span>
        <span className="inline-flex items-center gap-phi-2">
          <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: bandColors.monitor }} aria-hidden />
          Monitor {boundaries.passMonitorBoundary}–{monitorMax}
        </span>
        <span className="inline-flex items-center gap-phi-2">
          <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: bandColors.invest }} aria-hidden />
          Invest {boundaries.monitorInvestBoundary}–100
        </span>
      </div>
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
  compact = false,
}: {
  /** Slimmer bar and tighter gaps, for the two-page dock panel. */
  compact?: boolean;
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
    <div className={`flex flex-col ${compact ? 'gap-phi-3' : 'gap-phi-6'}`}>
      {!validation.valid && (
        <div className="border-l-2 border-escalation/45 px-phi-4 py-phi-3">
          {validation.errors.map((error) => (
            <p key={error} className="type-body-sm text-escalation/75">{error}</p>
          ))}
        </div>
      )}

      <p className="type-note text-oxford/70">
        {compact
          ? 'Below the auto-pass threshold, deals skip further review.'
          : 'Drag a marker, use arrow keys, or enter an exact score. Auto-pass skips further review below its threshold.'}
      </p>

      <ThresholdBar boundaries={boundaries} onChange={applyBounds} compact={compact} />

      {/* Column order matches the markers left-to-right on the bar. */}
      <div className={`grid sm:grid-cols-3 ${compact ? 'gap-phi-4' : 'gap-phi-5'}`}>
        <ScoreInput
          id="auto-pass-below"
          label="Auto-pass threshold"
          value={boundaries.autoPassCeiling}
          min={0}
          max={boundaries.passMonitorBoundary - 1}
          onCommit={(value) => applyBounds({ autoPassCeiling: value })}
        />
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
      </div>

      <div className={`grid sm:grid-cols-2 ${compact ? 'gap-phi-4' : 'gap-phi-7 pt-phi-5'}`}>
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
          label="Minimum scout confidence (0–1)"
          value={draft.thresholds.confidenceFloor}
          min={0}
          max={1}
          onCommit={(value) => updateThreshold('confidenceFloor', value)}
        />
      </div>
    </div>
  );
}
