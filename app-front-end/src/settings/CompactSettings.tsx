import { useState, type ReactNode } from 'react';
import type {
  FundConfiguration,
  MemoStyle,
  MemoTone,
  RiskSensitivity,
  ScoringDimensionKey,
} from '../lib/fundConfiguration';
import DecisionThresholdsPanel from './DecisionThresholdsPanel';
import { StepButton, WeightInput } from './WeightControls';

/**
 * Compact bodies for the dock pullout. Same fields, same handlers, same section
 * ids as the full page (scroll and attention routing look sections up by id) —
 * only the layout differs: one line per setting, label left, control right.
 * State and validation stay owned by SettingsPage.
 */

type UpdateDraft = (updater: (current: FundConfiguration) => FundConfiguration) => void;

const RISK_HINTS: Record<RiskSensitivity, string> = {
  conservative: 'Surface more risk',
  balanced: 'Standard review',
  aggressive: 'Surface only stronger risk',
};

function Section({ id, title, aside, children }: { id: string; title: string; aside?: ReactNode; children: ReactNode }) {
  return (
    <section id={id} tabIndex={-1} className="compact-section outline-none">
      <div className="flex items-baseline justify-between gap-phi-3 pb-phi-1">
        <h2 className="type-label-section">{title}</h2>
        {aside}
      </div>
      {children}
    </section>
  );
}

function Row({ id, label, hint, children }: { id?: string; label: string; hint?: string; children: ReactNode }) {
  return (
    <div className="flex min-h-9 items-center justify-between gap-phi-4 py-phi-1">
      <div className="min-w-0">
        {id ? (
          <label htmlFor={id} className="type-body-sm text-oxford">{label}</label>
        ) : (
          <span className="type-body-sm text-oxford">{label}</span>
        )}
        {hint ? <p className="type-note text-oxford/60">{hint}</p> : null}
      </div>
      <div className="flex min-w-0 items-center justify-end gap-phi-2">{children}</div>
    </div>
  );
}

function TextCell({
  id,
  value,
  onChange,
  label,
  type = 'text',
  width = 'w-44',
  min,
  max,
}: {
  id: string;
  value: string | number;
  onChange: (value: string) => void;
  /** Accessible name when the visible label sits on the row rather than the input. */
  label?: string;
  type?: 'text' | 'number';
  width?: string;
  min?: number;
  max?: number;
}) {
  return (
    <input
      id={id}
      type={type}
      min={min}
      max={max}
      aria-label={label}
      value={value}
      onChange={(event) => onChange(event.target.value)}
      className={`compact-field type-body-sm ${width}`}
    />
  );
}

/** Every option visible as a pill, label above — a selection you can read at a glance. */
function ChipRow({
  id,
  label,
  options,
  selected,
  onChange,
}: {
  id: string;
  label: string;
  options: string[];
  selected: string[];
  onChange: (value: string[]) => void;
}) {
  const toggle = (option: string) => {
    onChange(selected.includes(option) ? selected.filter((item) => item !== option) : [...selected, option]);
  };

  return (
    <div role="group" aria-labelledby={`${id}-label`} className="py-phi-1">
      <p id={`${id}-label`} className="type-body-sm pb-phi-1 text-oxford">{label}</p>
      <div className="flex flex-wrap gap-phi-2">
        {options.map((option) => (
          <button
            key={option}
            type="button"
            aria-pressed={selected.includes(option)}
            onClick={() => toggle(option)}
            className="settings-choice type-action inline-flex items-center justify-center"
          >
            {option}
          </button>
        ))}
      </div>
    </div>
  );
}

function Segmented<T extends string>({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: T;
  options: Array<{ value: T; label: string }>;
  onChange: (value: T) => void;
}) {
  return (
    <div role="radiogroup" aria-label={label} className="compact-seg">
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          role="radio"
          aria-checked={option.value === value}
          onClick={() => onChange(option.value)}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

function SwitchRow({
  id,
  label,
  hint,
  checked,
  onChange,
}: {
  id: string;
  label: string;
  hint?: string;
  checked: boolean;
  onChange: (value: boolean) => void;
}) {
  return (
    <Row id={id} label={label} hint={hint}>
      <button id={id} type="button" role="switch" aria-checked={checked} onClick={() => onChange(!checked)} className="compact-switch" />
    </Row>
  );
}

function NarrativeRow({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  const [open, setOpen] = useState(false);
  return (
    <div>
      <Row id="thesis-narrative-toggle" label="Notes / thesis text">
        <button
          id="thesis-narrative-toggle"
          type="button"
          aria-expanded={open}
          aria-controls="thesis-text"
          onClick={() => setOpen((current) => !current)}
          className="compact-summary type-body-sm"
        >
          <span className="truncate">{value.trim() || 'Add notes'}</span>
          <span aria-hidden>{open ? '▴' : '▾'}</span>
        </button>
      </Row>
      {open ? (
        <textarea
          id="thesis-text"
          aria-label="Notes / thesis text"
          rows={6}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          className="compact-field type-body-sm w-full resize-y !text-left leading-relaxed"
        />
      ) : null}
    </div>
  );
}

export function CompactThesis({
  draft,
  updateMandate,
  options,
  liveThesis,
}: {
  draft: FundConfiguration;
  updateMandate: <K extends keyof FundConfiguration['mandate']>(key: K, value: FundConfiguration['mandate'][K]) => void;
  options: { stages: string[]; geographies: string[]; sectors: string[] };
  liveThesis: string;
}) {
  const { mandate } = draft;
  return (
    <div className="compact-body">
      <Section id="thesis" title="Identity">
        <Row id="fund-name" label="Fund name">
          <TextCell id="fund-name" value={mandate.fundName} onChange={(value) => updateMandate('fundName', value)} />
        </Row>
        <Row id="mandate-name" label="Mandate name">
          <TextCell id="mandate-name" value={mandate.mandateName} onChange={(value) => updateMandate('mandateName', value)} />
        </Row>
      </Section>

      <Section id="where-to-invest" title="Where to invest">
        <ChipRow id="preferred-stages" label="Preferred stages" options={options.stages} selected={mandate.preferredStages} onChange={(value) => updateMandate('preferredStages', value)} />
        <ChipRow id="geographies" label="Geographies" options={options.geographies} selected={mandate.geographies} onChange={(value) => updateMandate('geographies', value)} />
        <Row id="custom-geography" label="Custom geography">
          <TextCell id="custom-geography" value={mandate.customGeography} onChange={(value) => updateMandate('customGeography', value)} />
        </Row>
      </Section>

      <Section id="what-to-invest-in" title="What to invest in">
        <ChipRow id="sectors" label="Sectors" options={options.sectors} selected={mandate.sectors} onChange={(value) => updateMandate('sectors', value)} />
        <Row id="custom-sectors" label="Custom sectors">
          <TextCell id="custom-sectors" value={mandate.customSectors} onChange={(value) => updateMandate('customSectors', value)} />
        </Row>
        <Row id="excluded-sectors" label="Excluded sectors">
          <TextCell id="excluded-sectors" value={mandate.excludedSectors} onChange={(value) => updateMandate('excludedSectors', value)} />
        </Row>
        <Row id="business-models" label="Preferred business models">
          <TextCell id="business-models" value={mandate.businessModels} onChange={(value) => updateMandate('businessModels', value)} />
        </Row>
      </Section>

      <Section id="economics" title="Economics">
        <Row id="check-min" label="Check size (USD)">
          <TextCell id="check-min" type="number" min={0} width="w-28" label="Minimum check size (USD)" value={mandate.checkSizeMin} onChange={(value) => updateMandate('checkSizeMin', Number(value))} />
          <span aria-hidden className="text-oxford/40">–</span>
          <TextCell id="check-max" type="number" min={0} width="w-28" label="Maximum check size (USD)" value={mandate.checkSizeMax} onChange={(value) => updateMandate('checkSizeMax', Number(value))} />
        </Row>
        <Row id="ownership" label="Ownership target %">
          <TextCell id="ownership" type="number" min={0} max={100} width="w-20" value={mandate.ownershipTarget} onChange={(value) => updateMandate('ownershipTarget', Number(value))} />
        </Row>
      </Section>

      <Section id="proof-required" title="Proof required">
        <Row id="minimum-traction" label="Minimum traction expectations">
          <TextCell id="minimum-traction" value={mandate.minimumTraction} onChange={(value) => updateMandate('minimumTraction', value)} />
        </Row>
      </Section>

      <Section id="thesis-narrative" title="Thesis narrative">
        <NarrativeRow value={mandate.thesisText} onChange={(value) => updateMandate('thesisText', value)} />
      </Section>

      <Section id="version" title="Version">
        <Row label="Draft"><span className="type-body-sm text-oxford">{draft.versionLabel}</span></Row>
        <Row label="Live thesis"><span className="type-body-sm text-oxford">{liveThesis}</span></Row>
      </Section>
    </div>
  );
}

export default function CompactPolicy({
  draft,
  updateDraft,
  updateThreshold,
  updateRisk,
  updateMemo,
  setWeight,
  weightValidation,
  bandErrors,
}: {
  draft: FundConfiguration;
  updateDraft: UpdateDraft;
  updateThreshold: <K extends keyof FundConfiguration['thresholds']>(key: K, value: FundConfiguration['thresholds'][K]) => void;
  updateRisk: <K extends keyof FundConfiguration['risk']>(key: K, value: FundConfiguration['risk'][K]) => void;
  updateMemo: <K extends keyof FundConfiguration['memo']>(key: K, value: FundConfiguration['memo'][K]) => void;
  setWeight: (key: ScoringDimensionKey, value: number) => void;
  weightValidation: { valid: boolean; total: number };
  bandErrors: string[];
}) {
  return (
    <div className="compact-body">
      {bandErrors.length > 0 ? (
        <div className="compact-span border-l-2 border-escalation/45 py-phi-2 pl-phi-3">
          {bandErrors.map((error) => <p key={error} className="type-body-sm text-escalation/75">{error}</p>)}
        </div>
      ) : null}

      <Section id="thresholds" title="Investment decisions">
        <DecisionThresholdsPanel compact draft={draft} updateDraft={updateDraft} updateThreshold={updateThreshold} />
      </Section>

      <Section id="sensitivity" title="Escalation sensitivity">
        <Row label="Sensitivity" hint={RISK_HINTS[draft.risk.sensitivity]}>
          <Segmented<RiskSensitivity>
            label="Sensitivity"
            value={draft.risk.sensitivity}
            options={[
              { value: 'conservative', label: 'Conservative' },
              { value: 'balanced', label: 'Balanced' },
              { value: 'aggressive', label: 'Aggressive' },
            ]}
            onChange={(value) => updateRisk('sensitivity', value)}
          />
        </Row>
      </Section>

      <Section
        id="weights"
        title="Scoring weights"
        aside={(
          <span
            title="Set one — the other four split the remainder in proportion to each other"
            className={`type-data ${weightValidation.valid ? 'text-oxford' : 'text-escalation/75'}`}
          >
            {weightValidation.total}%
          </span>
        )}
      >
        <div className="grid grid-cols-5 gap-phi-2">
          {draft.scoringWeights.map((item) => (
            <div key={item.key} className="compact-weight">
              <span className="type-note truncate text-oxford/60">{item.label}</span>
              <WeightInput
                label={item.label}
                value={item.weight}
                onCommit={(value) => setWeight(item.key, value)}
                className="type-data w-full border-0 bg-transparent p-0 text-center !text-lg leading-none text-oxford outline-none focus:ring-0"
              />
              <div className="flex items-center">
                <StepButton label={`Decrease ${item.label} weight`} disabled={item.weight <= 0} onClick={() => setWeight(item.key, item.weight - 1)}>−</StepButton>
                <StepButton label={`Increase ${item.label} weight`} disabled={item.weight >= 100} onClick={() => setWeight(item.key, item.weight + 1)}>+</StepButton>
              </div>
            </div>
          ))}
        </div>
      </Section>

      <Section id="memo" title="Memo output">
        <Row label="Memo style">
          <Segmented<MemoStyle>
            label="Memo style"
            value={draft.memo.style}
            options={[
              { value: 'concise', label: 'Concise' },
              { value: 'standard', label: 'Standard' },
              { value: 'detailed', label: 'Detailed' },
            ]}
            onChange={(value) => updateMemo('style', value)}
          />
        </Row>
        <Row label="Memo tone">
          <Segmented<MemoTone>
            label="Memo tone"
            value={draft.memo.tone}
            options={[
              { value: 'partner', label: 'Partner' },
              { value: 'analyst', label: 'Analyst' },
            ]}
            onChange={(value) => updateMemo('tone', value)}
          />
        </Row>
        <SwitchRow id="deep-dive-collapsed" label="Collapse deep dive by default" checked={draft.memo.deepDiveCollapsed} onChange={(value) => updateMemo('deepDiveCollapsed', value)} />
        <SwitchRow id="evidence-excerpts" label="Include evidence excerpts" checked={draft.memo.includeEvidenceExcerpts} onChange={(value) => updateMemo('includeEvidenceExcerpts', value)} />
        <SwitchRow id="missing-data" label="Include missing-data section" checked={draft.memo.includeMissingData} onChange={(value) => updateMemo('includeMissingData', value)} />
        <SwitchRow id="score-reasoning" label="Include score reasoning" checked={draft.memo.includeScoreReasoning} onChange={(value) => updateMemo('includeScoreReasoning', value)} />
        <SwitchRow id="source-confidence" label="Include source confidence" checked={draft.memo.includeSourceConfidence} onChange={(value) => updateMemo('includeSourceConfidence', value)} />
      </Section>

      <Section id="workflow" title="Ruling workflow">
        <SwitchRow id="risk-ack" label="Require acknowledgement before ruling" hint="High-risk pending deals need a reviewed-risk step before Commit." checked={draft.risk.requireAcknowledgement} onChange={(value) => updateRisk('requireAcknowledgement', value)} />
        <SwitchRow id="risk-high-only" label="Only gate high severity risks" hint="Medium adverse items stay visible without blocking the ruling." checked={draft.risk.onlyGateHighSeverity} onChange={(value) => updateRisk('onlyGateHighSeverity', value)} />
      </Section>
    </div>
  );
}
