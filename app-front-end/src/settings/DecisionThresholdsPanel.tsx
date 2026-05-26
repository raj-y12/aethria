import { useMemo } from 'react';
import {
  applyDecisionLadder,
  buildLadderPreviewExamples,
  formatReviewerScale,
  getDecisionLadderBoundaries,
  isDecisionLadderDrifted,
  validateDecisionLadder,
  type DecisionLadderBoundaries,
} from '../lib/decisionLadder';
import type { FundConfiguration } from '../lib/fundConfiguration';
import { DEFAULT_VERDICT_BADGES } from '../lib/fundConfiguration';

const labelCls = 'type-label-section text-oxford/45';
const metaCls = 'type-meta text-oxford/42';
const inputCls =
  'w-full rounded-none border-0 border-b border-oxford/[0.12] bg-transparent px-0 py-phi-2 type-body-sm font-mono tabular-nums text-oxford outline-none transition-colors placeholder:text-oxford/25 focus:border-oxford/45';

const bandColors = {
  pass: DEFAULT_VERDICT_BADGES.find((b) => b.id === 'PASS')?.backgroundColor ?? '#eabfb7',
  monitor: DEFAULT_VERDICT_BADGES.find((b) => b.id === 'MONITOR')?.backgroundColor ?? '#e5d39f',
  invest: DEFAULT_VERDICT_BADGES.find((b) => b.id === 'INVEST')?.backgroundColor ?? '#bfe3cc',
};

function LadderBar({ boundaries }: { boundaries: DecisionLadderBoundaries }) {
  const { autoPassCeiling, passMonitorBoundary, monitorInvestBoundary } = boundaries;
  const passWidth = Math.max(4, passMonitorBoundary);
  const monitorWidth = Math.max(4, monitorInvestBoundary - passMonitorBoundary);
  const investWidth = Math.max(4, 100 - monitorInvestBoundary);
  const weakMarker = Math.min(99, Math.max(0, autoPassCeiling));

  return (
    <div className="relative">
      <div className="flex h-10 w-full overflow-hidden rounded-none border border-oxford/[0.1]">
        <div
          className="flex min-w-0 items-center justify-center type-meta uppercase tracking-badge text-oxford/70"
          style={{ width: `${passWidth}%`, backgroundColor: bandColors.pass }}
          title={`Pass: 0–${passMonitorBoundary - 1}`}
        >
          Pass
        </div>
        <div
          className="flex min-w-0 items-center justify-center type-meta uppercase tracking-badge text-oxford/70"
          style={{ width: `${monitorWidth}%`, backgroundColor: bandColors.monitor }}
          title={`Monitor: ${passMonitorBoundary}–${monitorInvestBoundary - 1}`}
        >
          Monitor
        </div>
        <div
          className="flex min-w-0 flex-1 items-center justify-center type-meta uppercase tracking-badge text-oxford/70"
          style={{ width: `${investWidth}%`, backgroundColor: bandColors.invest }}
          title={`Invest: ${monitorInvestBoundary}–100`}
        >
          Invest
        </div>
      </div>
      <div
        className="pointer-events-none absolute top-0 bottom-0 w-px bg-oxford/50"
        style={{ left: `${weakMarker}%` }}
        aria-hidden
      />
      <p className="mt-phi-2 type-meta text-oxford/40">
        Bar = grid bands (weighted 0–100 score). Vertical tick = weak-deal ceiling ({autoPassCeiling}).
      </p>
    </div>
  );
}

function BoundaryField({
  id,
  label,
  hint,
  value,
  min,
  max,
  step,
  onChange,
}: {
  id: string;
  label: string;
  hint: string;
  value: number;
  min: number;
  max: number;
  step?: number;
  onChange: (value: number) => void;
}) {
  return (
    <div className="flex min-w-0 flex-col gap-phi-2">
      <label htmlFor={id} className={labelCls}>{label}</label>
      <input
        id={id}
        type="number"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(event) => onChange(Number(event.target.value) || 0)}
        className={inputCls}
      />
      <p className={metaCls}>{hint}</p>
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
  const boundaries = useMemo(() => getDecisionLadderBoundaries(draft), [draft]);
  const ladderValidation = useMemo(() => validateDecisionLadder(draft), [draft]);
  const drifted = useMemo(() => isDecisionLadderDrifted(draft), [draft]);
  const examples = useMemo(() => buildLadderPreviewExamples(draft), [draft]);

  const applyLadder = (patch: Partial<DecisionLadderBoundaries>) => {
    updateDraft((current) => applyDecisionLadder(current, patch));
  };

  return (
    <div className="flex flex-col gap-phi-7">
      {drifted && (
        <div className="border border-oxford/[0.12] bg-oxford/[0.03] px-phi-4 py-phi-3">
          <p className="type-body-sm text-oxford/62">
            Verdict badge ranges and Partner thresholds were out of sync. Adjusting the ladder below aligns both on save.
          </p>
        </div>
      )}
      {!ladderValidation.valid && (
        <div className="border border-escalation/25 bg-escalation/[0.035] px-phi-4 py-phi-3">
          {ladderValidation.errors.map((error) => (
            <p key={error} className="type-body-sm text-escalation/75">{error}</p>
          ))}
        </div>
      )}

      <div className="flex flex-col gap-phi-4">
        <p className="type-body-sm leading-relaxed text-oxford/52">
          One ladder drives <span className="font-medium text-oxford/72">grid labels</span> (weighted score) and{' '}
          <span className="font-medium text-oxford/72">Partner bars</span> (reviewer 1–10 average, stored as 0–100 here).
          Grey-zone and LLM triggers remain in backend policy v1.1.
        </p>
        <LadderBar boundaries={boundaries} />
      </div>

      <div className="border-t border-oxford/[0.055] pt-phi-5">
        <p className={labelCls}>Investment ladder</p>
        <div className="mt-phi-4 grid gap-phi-5 md:grid-cols-2">
          <BoundaryField
            id="ladder-pass-monitor"
            label="Pass → Monitor boundary"
            hint={`Weighted scores ≥ ${boundaries.passMonitorBoundary} show Monitor; Partner funnel bar ${formatReviewerScale(boundaries.passMonitorBoundary)} avg.`}
            value={boundaries.passMonitorBoundary}
            min={2}
            max={99}
            onChange={(value) => applyLadder({ passMonitorBoundary: value })}
          />
          <BoundaryField
            id="ladder-monitor-invest"
            label="Monitor → Invest boundary"
            hint={`Weighted scores ≥ ${boundaries.monitorInvestBoundary} show Invest; Partner strong bar ${formatReviewerScale(boundaries.monitorInvestBoundary)} avg.`}
            value={boundaries.monitorInvestBoundary}
            min={3}
            max={100}
            onChange={(value) => applyLadder({ monitorInvestBoundary: value })}
          />
          <BoundaryField
            id="ladder-auto-pass"
            label="Weak-deal ceiling"
            hint={`Below ${boundaries.autoPassCeiling} (${formatReviewerScale(boundaries.autoPassCeiling)} avg): Partner auto-pass lean on borderline deals.`}
            value={boundaries.autoPassCeiling}
            min={0}
            max={Math.max(0, boundaries.passMonitorBoundary - 1)}
            onChange={(value) => applyLadder({ autoPassCeiling: value })}
          />
        </div>
      </div>

      <div className="border-t border-oxford/[0.055] pt-phi-5">
        <p className={labelCls}>Examples at current settings</p>
        <div className="mt-phi-3 overflow-x-auto">
          <table className="w-full min-w-[32rem] border-collapse text-left">
            <thead>
              <tr className="border-b border-oxford/[0.08]">
                <th className="py-phi-2 pr-phi-3 type-meta text-oxford/40">Weighted score</th>
                <th className="py-phi-2 pr-phi-3 type-meta text-oxford/40">Grid label</th>
                <th className="py-phi-2 pr-phi-3 type-meta text-oxford/40">Reviewer avg</th>
                <th className="py-phi-2 type-meta text-oxford/40">Partner path</th>
              </tr>
            </thead>
            <tbody>
              {examples.map((row) => (
                <tr key={`${row.weightedScore}-${row.reviewerAvg}`} className="border-b border-oxford/[0.05]">
                  <td className="py-phi-2 pr-phi-3 font-mono text-sm tabular-nums text-oxford">{row.weightedScore}</td>
                  <td className="py-phi-2 pr-phi-3 type-body-sm text-oxford/62">{row.gridLabel}</td>
                  <td className="py-phi-2 pr-phi-3 font-mono text-sm tabular-nums text-oxford/72">{row.reviewerAvg.toFixed(1)}</td>
                  <td className="py-phi-2 type-body-sm text-oxford/52">{row.partnerNote}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="border-t border-oxford/[0.055] pt-phi-5">
        <p className={labelCls}>Queue hygiene</p>
        <p className="mt-phi-2 type-body-sm text-oxford/48">
          Unresolved deals surface in the Stale queue after this period (human-resolved deals are excluded).
        </p>
        <div className="mt-phi-4 max-w-xs">
          <BoundaryField
            id="stale-after"
            label="Stale after (hours)"
            hint="Work grid copy and Stale filter use this value."
            value={draft.thresholds.staleAfterHours}
            min={1}
            max={720}
            onChange={(value) => updateThreshold('staleAfterHours', value)}
          />
        </div>
      </div>

      <div className="border-t border-oxford/[0.055] pt-phi-5">
        <p className={labelCls}>Evidence strictness</p>
        <p className="mt-phi-2 type-body-sm text-oxford/48">
          Flags in agent traces when scout confidence is low or dossiers are thin — they do not replace Partner rules.
        </p>
        <div className="mt-phi-4 grid gap-phi-5 md:grid-cols-2">
          <BoundaryField
            id="confidence-floor"
            label="Scout confidence floor"
            hint="0–1 scale. Scouts below this are flagged in pipeline traces."
            value={draft.thresholds.confidenceFloor}
            min={0}
            max={1}
            step={0.01}
            onChange={(value) => updateThreshold('confidenceFloor', Math.min(1, Math.max(0, value)))}
          />
          <BoundaryField
            id="missing-data-threshold"
            label="Missing-data reference (%)"
            hint="Recorded in reviewer handoff policy for explainability."
            value={draft.thresholds.missingDataThreshold}
            min={0}
            max={100}
            onChange={(value) => updateThreshold('missingDataThreshold', value)}
          />
        </div>
      </div>
    </div>
  );
}
