import { useEffect, useMemo, useRef, useState, type CSSProperties } from 'react';
import { useNavigate } from 'react-router';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import LoadingAnimation from '../components/LoadingAnimation';
import { getQueryConfig } from '../lib/queryIntent';
import { formatDateTime } from '../lib/dates';
import { useAppFrame } from '../components/AppFrame';
import { SpineNavButton } from '../components/SystemBar';
import { fetchSettings, patchSettings, previewPolicy, publishPolicy, type Settings } from '../api/settings';
import { fetchAgentsStatus, type AgentsStatus } from '../api/agents';
import {
  fetchFundThesisSummary,
  postFundThesisVersion,
  type FundThesisSummary,
} from '../api/fundThesis';
import DecisionBadge from '../components/DecisionBadge';
import { useFundConfiguration } from '../hooks';
import DecisionThresholdsPanel from './DecisionThresholdsPanel';
import { validateDecisionThresholds } from '../lib/decisionThresholds';
import {
  applyThesisVersionMetadata,
  buildFundConfigThesisPayload,
  clearFundConfiguration,
  getWeightImpactText,
  mapFundConfigToSettings,
  thesisVersionLabel,
  rebalanceWeights,
  validateScoreBands,
  validateWeights,
  type FundConfiguration,
  type MemoStyle,
  type MemoTone,
  type RiskSensitivity,
} from '../lib/fundConfiguration';

type SectionId =
  | 'mandate'
  | 'memo'
  | 'risk'
  | 'thresholds'
  | 'budget'
  | 'weights';

const SELECT_CHEVRON =
  "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='10' viewBox='0 0 10 10'%3E%3Cpath fill='%231a2b48' fill-opacity='0.45' d='M0 3h10L5 8z'/%3E%3C/svg%3E\")";

const selectStyle: CSSProperties = { backgroundImage: SELECT_CHEVRON };

const sections: Array<{ id: SectionId; label: string; short: string }> = [
  { id: 'mandate', label: 'Fund Mandate', short: 'Mandate' },
  { id: 'memo', label: 'Memo Output', short: 'Memo' },
  { id: 'risk', label: 'Ruling', short: 'Ruling' },
  { id: 'thresholds', label: 'Decision Thresholds', short: 'Thresholds' },
  { id: 'budget', label: 'Operations', short: 'Operations' },
  { id: 'weights', label: 'Scoring Weights', short: 'Weights' },
];

const stageOptions = ['Pre-seed', 'Seed', 'Series A', 'Series B+'];
const geographyOptions = ['US', 'Europe', 'UK/Ireland', 'Global'];
const sectorOptions = ['B2B SaaS', 'AI', 'Infrastructure', 'Fintech', 'Healthcare', 'Devtools', 'Climate'];
const inputCls =
  'w-full rounded-none border-0 border-b border-oxford/[0.12] bg-transparent px-0 py-phi-2 type-body-sm text-oxford outline-none transition-colors placeholder:text-oxford/25 focus:border-oxford/45';
const selectCls =
  `${inputCls} cursor-pointer appearance-none bg-no-repeat bg-[length:10px] bg-[center_right_2px] pr-7`;
const labelCls = 'type-label-section text-oxford/45';
const sectionLabelCls = 'type-label-section text-oxford/[0.72]';
const metaCls = 'type-meta text-oxford/[0.42]';
const actionBtnCls =
  'type-label-section inline-flex min-h-[36px] items-center rounded-none border-0 bg-transparent p-0 text-oxford/55 transition-colors hover:text-oxford disabled:cursor-not-allowed disabled:opacity-30 btn-interaction focus:outline-none focus-visible:ring-2 focus-visible:ring-oxford/30';
const solidBtnCls =
  'type-label-section inline-flex min-h-[36px] items-center justify-center rounded-none bg-oxford px-phi-4 text-paper transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40 btn-interaction focus:outline-none focus-visible:ring-2 focus-visible:ring-oxford/30';

function serializeConfig(config: FundConfiguration): string {
  const rest = { ...config } as Record<string, unknown>;
  for (const key of ['lastSavedAt', 'version', 'versionLabel', 'activePolicyVersionId', 'draftPolicyHash', 'publishedPolicyHash', 'lastPublishedAt']) {
    delete rest[key];
  }
  return JSON.stringify(rest);
}

function SettingsSidebarFooter({
  unsaved,
  lastSavedAt,
  saving,
  onSave,
  onReset,
}: {
  unsaved: boolean;
  lastSavedAt?: string | null;
  saving: boolean;
  onSave: () => void;
  onReset: () => void;
}) {
  const statusDetail = unsaved
    ? 'Changes not yet saved'
    : lastSavedAt
      ? `Saved · ${formatSettingsSavedAt(lastSavedAt)}`
      : 'Save to persist fund configuration';

  return (
    <div
      className="mt-phi-6 min-w-0 shrink-0 border-t border-oxford/[0.075] pt-phi-4"
      aria-label="Draft status"
    >
      <div className="flex items-center justify-between gap-phi-2">
        <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-oxford/40">Draft</span>
        <span
          className={`inline-flex shrink-0 items-center gap-phi-2 font-mono text-[10px] uppercase tracking-[0.10em] transition-colors ${unsaved ? 'text-escalation/80' : 'text-oxford/45'}`}
          aria-live="polite"
        >
          <span
            className={`h-1.5 w-1.5 shrink-0 rounded-none signal-dot-breathe transition-colors ${unsaved ? 'bg-escalation/70' : 'bg-oxford'}`}
            aria-hidden
          />
          {unsaved ? 'Unsaved' : 'Synced'}
        </span>
      </div>
      <p className={`mt-phi-2 truncate type-body-sm leading-snug transition-colors ${unsaved ? 'text-oxford' : 'text-oxford/50'}`}>
        {statusDetail}
      </p>
      <div className="mt-phi-4 flex flex-col gap-phi-2">
        <button
          type="button"
          onClick={onSave}
          disabled={saving || !unsaved}
          className="w-full btn-aethria-solid disabled:cursor-not-allowed disabled:opacity-40"
        >
          {saving ? 'Saving…' : 'Save changes'}
        </button>
        <button
          type="button"
          onClick={onReset}
          disabled={saving}
          className={`${actionBtnCls} w-full justify-center`}
          title="Restore local defaults; save to sync compatible fields to the backend"
        >
          Reset to defaults
        </button>
      </div>
    </div>
  );
}

function serializeOperations(settings: Settings | null): string {
  if (!settings) return '';
  return JSON.stringify({
    agent_config: settings.agent_config,
    cost_budget: settings.cost_budget,
  });
}

function formatSettingsSavedAt(iso: string): string {
  const formatted = formatDateTime(iso);
  return formatted === '—' ? 'Saved' : formatted;
}

function TextField({
  id,
  label,
  value,
  onChange,
  hint,
  disabled = false,
  type = 'text',
  min,
  max,
  step,
}: {
  id: string;
  label: string;
  value: string | number;
  onChange: (value: string | number) => void;
  hint?: string;
  disabled?: boolean;
  type?: 'text' | 'number';
  min?: number;
  max?: number;
  step?: number;
}) {
  return (
    <div className="flex min-w-0 flex-col gap-phi-2">
      <label htmlFor={id} className={labelCls}>{label}</label>
      <input
        id={id}
        type={type}
        min={min}
        max={max}
        step={step}
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(type === 'number' ? Number(event.target.value) || 0 : event.target.value)}
        className={`${inputCls} disabled:cursor-not-allowed disabled:text-oxford/35 disabled:opacity-60`}
      />
      {hint && <p className={metaCls}>{hint}</p>}
    </div>
  );
}

function TextAreaField({
  id,
  label,
  value,
  onChange,
  rows = 4,
  hint,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  rows?: number;
  hint?: string;
}) {
  return (
    <div className="flex flex-col gap-phi-2">
      <label htmlFor={id} className={labelCls}>{label}</label>
      <textarea
        id={id}
        rows={rows}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="w-full resize-y rounded-none border border-oxford/[0.08] bg-oxford/[0.025] px-phi-3 py-phi-3 type-body-sm leading-relaxed text-oxford outline-none transition-colors placeholder:text-oxford/25 focus:border-oxford/[0.28]"
      />
      {hint && <p className={metaCls}>{hint}</p>}
    </div>
  );
}

function ToggleRow({
  id,
  checked,
  onChange,
  label,
  hint,
}: {
  id: string;
  checked: boolean;
  onChange: (value: boolean) => void;
  label: string;
  hint?: string;
}) {
  return (
    <div className="flex items-center justify-between gap-phi-5 border-b border-oxford/[0.055] py-phi-3 last:border-0">
      <div className="min-w-0">
        <label htmlFor={id} className="type-body-sm text-oxford">{label}</label>
        {hint && <p className="mt-phi-1 type-meta leading-snug text-oxford/[0.38]">{hint}</p>}
      </div>
      <button
        id={id}
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={`h-6 w-11 shrink-0 rounded-none transition-colors ${checked ? 'bg-oxford' : 'bg-oxford/[0.09]'}`}
      >
        <span className={`block h-4 w-4 rounded-none transition-transform ${checked ? 'translate-x-5 bg-paper' : 'translate-x-1 bg-oxford/35'}`} />
      </button>
    </div>
  );
}

function ChipGroup({
  label,
  options,
  selected,
  onChange,
}: {
  label: string;
  options: string[];
  selected: string[];
  onChange: (value: string[]) => void;
}) {
  const toggle = (option: string) => {
    onChange(selected.includes(option) ? selected.filter((item) => item !== option) : [...selected, option]);
  };
  return (
    <div className="flex flex-col gap-phi-3">
      <p className={labelCls}>{label}</p>
      <div className="flex flex-wrap gap-phi-2">
        {options.map((option) => {
          const active = selected.includes(option);
          return (
            <button
              key={option}
              type="button"
              aria-pressed={active}
              onClick={() => toggle(option)}
              className={`type-meta inline-flex min-h-[36px] items-center justify-center rounded-none px-phi-3 transition-colors ${active ? 'bg-oxford text-paper' : 'bg-oxford/[0.045] text-oxford/[0.58] hover:bg-oxford/[0.075]'}`}
            >
              {option}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function SettingsSection({
  id,
  title,
  kicker,
  children,
  className,
}: {
  id: SectionId;
  title: string;
  kicker: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section id={id} className={`border-t border-oxford/[0.075] py-phi-7 first:border-t-0 first:pt-0 ${className ?? ''}`}>
      <div className="grid gap-phi-6 xl:grid-cols-[minmax(180px,24%)_minmax(0,1fr)]">
        <div>
          <p className={sectionLabelCls}>{title}</p>
          <p className="mt-phi-3 max-w-[17rem] type-body-sm leading-relaxed text-oxford/45">{kicker}</p>
        </div>
        <div className="min-w-0">{children}</div>
      </div>
    </section>
  );
}

function PreviewPanel({
  config,
  unsaved,
  lastSavedAt,
  saving,
  onSave,
  onReset,
}: {
  config: FundConfiguration;
  unsaved: boolean;
  lastSavedAt?: string | null;
  saving: boolean;
  onSave: () => void;
  onReset: () => void;
}) {
  const weightTotal = validateWeights(config.scoringWeights).total;
  return (
    <aside className="relative hidden min-h-full shrink-0 self-stretch border-l border-oxford/[0.08] xl:block">
      <div className="sticky top-0 z-[1] flex max-h-[calc(100dvh)] flex-col overflow-y-auto bg-paper px-phi-5 pt-phi-6 pb-phi-6">
        <p className="type-label-section text-oxford/55">Configuration Preview</p>
        <div className="mt-phi-4 flex flex-col gap-phi-5">
          <div>
            <p className="type-meta text-oxford/35">Mandate</p>
            <p className="mt-phi-2 type-body-emphasis text-oxford">{config.mandate.fundName || 'Unnamed fund'}</p>
            <p className="mt-phi-1 type-body-sm text-oxford/[0.52]">
              {[...config.mandate.preferredStages, ...config.mandate.geographies].filter(Boolean).join(' · ') || 'No mandate scope set'}
            </p>
          </div>
          <div className="border-t border-oxford/[0.06] pt-phi-4">
            <p className="type-meta text-oxford/35">Total scoring weight</p>
            <p className={`mt-phi-2 font-mono text-[1.65rem] tabular-nums ${weightTotal === 100 ? 'text-oxford' : 'text-escalation/75'}`}>{weightTotal}%</p>
          </div>
          <div className="border-t border-oxford/[0.06] pt-phi-4">
            <p className="type-meta text-oxford/35">Verdict marks</p>
            <div className="mt-phi-3 flex flex-wrap gap-phi-2">
              {(['INVEST', 'MONITOR', 'PASS'] as const).map((id) => (
                <DecisionBadge key={id} variant={id} />
              ))}
            </div>
          </div>
          <div className="border-t border-oxford/[0.06] pt-phi-4">
            <p className="type-meta text-oxford/35">Score cutoffs</p>
            <div className="mt-phi-3 flex flex-col gap-phi-2">
              {config.scoreBands.map((item) => (
                <p key={item.id} className="type-meta text-oxford/[0.52]">
                  <span className="font-mono tabular-nums">{item.min}–{item.max}</span> {item.label}
                </p>
              ))}
              <p className="type-meta text-oxford/[0.38]">
                Stale after {config.thresholds.staleAfterHours}h · confidence ≥ {config.thresholds.confidenceFloor}
              </p>
            </div>
          </div>
          <div className="border-t border-oxford/[0.06] pt-phi-4">
            <p className="type-meta text-oxford/35">Risk gating</p>
            <p className="mt-phi-2 type-body-sm text-oxford/55">
              {config.risk.requireAcknowledgement ? `${config.risk.sensitivity} sensitivity` : 'Acknowledgement disabled'}
            </p>
          </div>
        </div>
        <SettingsSidebarFooter
          unsaved={unsaved}
          lastSavedAt={lastSavedAt}
          saving={saving}
          onSave={onSave}
          onReset={onReset}
        />
      </div>
    </aside>
  );
}

export default function SettingsPage() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const { setSpineOverride } = useAppFrame();

  const [settings, setSettings] = useState<Settings | null>(null);
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [errors, setErrors] = useState<string[]>([]);
  const [activeSection, setActiveSection] = useState<SectionId>('mandate');
  const [agentsStatus, setAgentsStatus] = useState<AgentsStatus | null>(null);
  const [thesisSummary, setThesisSummary] = useState<FundThesisSummary | null>(null);
  const [thesisBusy, setThesisBusy] = useState(false);
  const [policyBusy, setPolicyBusy] = useState(false);
  const [policyPreviewHash, setPolicyPreviewHash] = useState<string | null>(null);
  const [savedSnapshot, setSavedSnapshot] = useState('');
  const [savedOperationsSnapshot, setSavedOperationsSnapshot] = useState('');
  const contentScrollRef = useRef<HTMLDivElement | null>(null);

  const { configuration, setConfiguration, save: saveLocalConfiguration } = useFundConfiguration(settings);
  const [draft, setDraft] = useState<FundConfiguration>(configuration);

  // Settings ride the shared ['settings'] cache (also fed by useSystemData):
  // returning visitors get the page instantly instead of a loading takeover.
  const settingsQuery = useQuery({
    queryKey: ['settings'],
    queryFn: () => fetchSettings().catch(() => null),
    ...getQueryConfig('STATIC'),
  });

  // Seed the editable draft once — later refetches (e.g. after invalidation)
  // must never clobber in-progress edits.
  const seededRef = useRef(false);
  useEffect(() => {
    if (seededRef.current || !settingsQuery.data) return;
    seededRef.current = true;
    setSettings(settingsQuery.data);
    setSavedOperationsSnapshot(serializeOperations(settingsQuery.data));
  }, [settingsQuery.data]);

  const loading = settings == null && settingsQuery.isPending;

  useEffect(() => {
    let cancelled = false;
    fetchAgentsStatus().then((data) => { if (!cancelled) setAgentsStatus(data ?? null); }).catch(() => undefined);
    fetchFundThesisSummary().then((data) => { if (!cancelled) setThesisSummary(data); }).catch(() => undefined);
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    setDraft(configuration);
    setSavedSnapshot(serializeConfig(configuration));
  }, [configuration]);

  useEffect(() => {
    const versionNumber = thesisSummary?.active_version_number;
    if (versionNumber == null || versionNumber < 1) return;
    setConfiguration((current) => applyThesisVersionMetadata(current, versionNumber));
    setDraft((current) => applyThesisVersionMetadata(current, versionNumber));
  }, [thesisSummary?.active_version_number]);

  useEffect(() => {
    const root = contentScrollRef.current;
    if (!root) return;

    const targets = sections
      .map((section) => root.querySelector<HTMLElement>(`#${section.id}`))
      .filter((node): node is HTMLElement => node != null);
    if (!targets.length) return;

    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((entry) => entry.isIntersecting)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio);
        if (!visible.length) return;
        const id = visible[0].target.getAttribute('id') as SectionId | null;
        if (id) setActiveSection(id);
      },
      {
        root,
        // Favor the section currently near the top of the scroll viewport.
        rootMargin: '-20% 0px -65% 0px',
        threshold: [0, 0.15, 0.35, 0.6],
      }
    );

    targets.forEach((target) => observer.observe(target));
    return () => observer.disconnect();
  }, [loading, settings]);

  const weightValidation = useMemo(() => validateWeights(draft.scoringWeights), [draft.scoringWeights]);
  const bandValidation = useMemo(() => validateScoreBands(draft.scoreBands), [draft.scoreBands]);
  const thresholdValidation = useMemo(() => validateDecisionThresholds(draft), [draft]);
  const unsaved = serializeConfig(draft) !== savedSnapshot || serializeOperations(settings) !== savedOperationsSnapshot;
  const policyUnpublished = !!policyPreviewHash && policyPreviewHash !== draft.publishedPolicyHash;
  const thesisPublishDisabledReason = agentsStatus == null
    ? 'Checking storage readiness...'
    : !agentsStatus.supabase_configured
      ? 'Supabase storage is required to publish fund thesis versions.'
      : null;

  const updateDraft = (updater: (current: FundConfiguration) => FundConfiguration) => {
    setDraft((current) => updater(current));
    setStatus(null);
    setErrors([]);
  };

  const updateMandate = <K extends keyof FundConfiguration['mandate']>(key: K, value: FundConfiguration['mandate'][K]) =>
    updateDraft((current) => ({ ...current, mandate: { ...current.mandate, [key]: value } }));

  const updateThreshold = <K extends keyof FundConfiguration['thresholds']>(key: K, value: FundConfiguration['thresholds'][K]) =>
    updateDraft((current) => ({ ...current, thresholds: { ...current.thresholds, [key]: value } }));

  const updateRisk = <K extends keyof FundConfiguration['risk']>(key: K, value: FundConfiguration['risk'][K]) =>
    updateDraft((current) => ({ ...current, risk: { ...current.risk, [key]: value } }));

  const updateMemo = <K extends keyof FundConfiguration['memo']>(key: K, value: FundConfiguration['memo'][K]) =>
    updateDraft((current) => ({ ...current, memo: { ...current.memo, [key]: value } }));

  const handleSave = async () => {
    if (!settings) return;
    const nextErrors = [
      ...(weightValidation.valid ? [] : [`Scoring weights total ${weightValidation.total}%, not 100%.`]),
      ...bandValidation.errors,
      ...thresholdValidation.errors,
    ];
    if (nextErrors.length) {
      setErrors(nextErrors);
      return;
    }
    setSaving(true);
    setErrors([]);
    setStatus(null);
    const mapped = mapFundConfigToSettings(draft, settings);
    const result = await patchSettings(mapped);
    if (result.error) {
      setSaving(false);
      setErrors(result.error.errors.length ? result.error.errors : [result.error.message]);
      return;
    }
    const saved = saveLocalConfiguration(result.data?.fund_config ?? draft);
    setConfiguration(saved);
    setDraft(saved);
    setSavedSnapshot(serializeConfig(saved));
    if (result.data) {
      setSettings(result.data);
      setSavedOperationsSnapshot(serializeOperations(result.data));
    }
    await queryClient.invalidateQueries({ queryKey: ['settings'] });
    const summary = await fetchFundThesisSummary().catch(() => null);
    if (summary?.active_version_number != null) {
      setThesisSummary(summary);
      const labeled = applyThesisVersionMetadata(saved, summary.active_version_number);
      setDraft(labeled);
      setConfiguration(labeled);
      setSavedSnapshot(serializeConfig(labeled));
    }
    setStatus(null);
    setSaving(false);
  };

  const handleReset = () => {
    const next = clearFundConfiguration(settings);
    setConfiguration(next);
    setDraft(next);
    setSavedSnapshot(serializeConfig(next));
    setStatus(null);
    setErrors([]);
  };

  // ── The spine is the only rail: project section nav + draft state into it. ──
  // Handlers are reached through a ref so the projection effect re-runs only
  // when displayed values change, never on handler identity.
  const lastSavedAt = draft.lastSavedAt;
  const spineActionsRef = useRef({ save: () => {}, reset: () => {} });
  spineActionsRef.current = { save: () => void handleSave(), reset: handleReset };

  useEffect(() => {
    const scrollToSection = (id: SectionId) => {
      setActiveSection(id);
      const target = contentScrollRef.current?.querySelector<HTMLElement>(`#${id}`);
      target?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    };
    const statusDetail = unsaved
      ? 'Changes not yet saved'
      : lastSavedAt
        ? `Saved · ${formatSettingsSavedAt(lastSavedAt)}`
        : 'Save to persist fund configuration';
    setSpineOverride({
      nav: (
        <>
          <SpineNavButton
            label="← Today"
            active={false}
            ariaPressed={false}
            compact
            surface="oxford"
            onClick={() => navigate('/v1')}
          />
          <p className="px-2 pb-phi-1 pt-phi-4 font-mono text-[10px] uppercase tracking-[0.12em] text-white/[0.38]">
            Configuration
          </p>
          {sections.map((section) => (
            <SpineNavButton
              key={section.id}
              label={section.label}
              active={activeSection === section.id}
              ariaPressed={activeSection === section.id}
              compact
              surface="oxford"
              onClick={() => scrollToSection(section.id)}
            />
          ))}
        </>
      ),
      footer: (
        <section aria-label="Draft status" className="border-t border-white/[0.07] px-2 pt-phi-3">
          <div className="flex items-center justify-between gap-phi-2">
            <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-white/[0.38]">Draft</span>
            <span
              className={`inline-flex shrink-0 items-center gap-phi-2 font-mono text-[10px] uppercase tracking-[0.10em] ${
                unsaved ? 'text-escalation-bright/90' : 'text-white/45'
              }`}
              aria-live="polite"
            >
              <span
                className={`h-1.5 w-1.5 shrink-0 rounded-none ${unsaved ? 'bg-escalation-bright/80' : 'bg-white/55'}`}
                aria-hidden
              />
              {unsaved ? 'Unsaved' : 'Synced'}
            </span>
          </div>
          <p className={`mt-phi-2 truncate font-sans text-[12px] leading-snug ${unsaved ? 'text-white/85' : 'text-white/45'}`}>
            {statusDetail}
          </p>
          <div className="mt-phi-3 flex flex-col gap-phi-2 xl:hidden">
            <button
              type="button"
              onClick={() => spineActionsRef.current.save()}
              disabled={saving || !unsaved}
              className="w-full btn-aethria-solid !bg-paper !text-oxford disabled:cursor-not-allowed disabled:opacity-40"
            >
              {saving ? 'Saving…' : 'Save changes'}
            </button>
            <button
              type="button"
              onClick={() => spineActionsRef.current.reset()}
              disabled={saving}
              className="inline-flex min-h-[32px] w-full items-center justify-center font-mono text-[10px] uppercase tracking-[0.12em] text-white/40 transition-colors hover:text-white/80 disabled:opacity-50 btn-interaction"
              title="Restore local defaults; save to sync compatible fields to the backend"
            >
              Reset to defaults
            </button>
          </div>
        </section>
      ),
    });
  }, [setSpineOverride, navigate, activeSection, unsaved, saving, lastSavedAt]);

  // Leaving the room returns the spine to the workspaces.
  useEffect(() => () => setSpineOverride(null), [setSpineOverride]);

  const handlePreviewPolicy = async () => {
    setPolicyBusy(true);
    setErrors([]);
    setStatus(null);
    const result = await previewPolicy(draft);
    setPolicyBusy(false);
    if (result.error || !result.policy) {
      setErrors(result.error?.errors.length ? result.error.errors : [result.error?.message ?? 'Policy preview failed']);
      return;
    }
    setPolicyPreviewHash(result.policy.policy_hash);
    setDraft((current) => ({ ...current, draftPolicyHash: result.policy?.policy_hash ?? null }));
    const warningText = result.warnings?.length ? ` Warnings: ${result.warnings.join(' ')}` : '';
    setStatus(`Policy preview ready. Draft hash ${result.policy.policy_hash}.${warningText}`);
  };

  const handlePublishPolicy = async () => {
    setPolicyBusy(true);
    setErrors([]);
    setStatus(null);
    const result = await publishPolicy(draft);
    setPolicyBusy(false);
    if (result.error || !result.policy) {
      setErrors(result.error?.errors.length ? result.error.errors : [result.error?.message ?? 'Policy publish failed']);
      return;
    }
    const published = {
      ...draft,
      activePolicyVersionId: result.policy.policy_version_id,
      publishedPolicyHash: result.policy.policy_hash,
      draftPolicyHash: result.policy.policy_hash,
      lastPublishedAt: result.policy.published_at ?? new Date().toISOString(),
    };
    setDraft(published);
    setConfiguration(published);
    setPolicyPreviewHash(result.policy.policy_hash);
    const refreshed = await fetchSettings().catch(() => null);
    if (refreshed) {
      setSettings(refreshed);
      setSavedOperationsSnapshot(serializeOperations(refreshed));
      if (refreshed.fund_config) {
        setDraft(refreshed.fund_config);
        setConfiguration(refreshed.fund_config);
        setSavedSnapshot(serializeConfig(refreshed.fund_config));
      }
    }
    await queryClient.invalidateQueries({ queryKey: ['settings'] });
    setStatus(`Published scoring policy ${result.policy.policy_version_id}. New reviews will use this version.`);
  };

  const publishThesis = async () => {
    setThesisBusy(true);
    setErrors([]);
    try {
      const payload = buildFundConfigThesisPayload(draft);
      const result = await postFundThesisVersion(payload.raw_text, {
        parsed_json: payload.parsed_json,
        skip_embedding: agentsStatus?.openai_configured !== true,
      });
      const summary = await fetchFundThesisSummary();
      setThesisSummary(summary);
      await queryClient.invalidateQueries({ queryKey: ['fund-thesis'] });
      const versionNumber = summary?.active_version_number ?? result.version_number;
      const labeled = applyThesisVersionMetadata(draft, versionNumber);
      setDraft(labeled);
      setConfiguration(labeled);
      setSavedSnapshot(serializeConfig(labeled));
      const unchanged = result.status === 'unchanged';
      setStatus(
        unchanged
          ? `Active fund thesis is already ${thesisVersionLabel(versionNumber)} — no new version created.`
          : agentsStatus?.openai_configured === true
            ? `Mandate published as ${thesisVersionLabel(versionNumber)}.`
            : `Mandate published as ${thesisVersionLabel(versionNumber)} (rule-based; embeddings skipped until OpenAI is configured).`
      );
    } catch (error: unknown) {
      setErrors([error instanceof Error ? error.message : 'Could not publish thesis']);
    } finally {
      setThesisBusy(false);
    }
  };

  // In-place loader — never a full-screen takeover. The spine (with this
  // page's section nav) stays mounted, so opening Settings doesn't "break".
  if (loading) {
    return (
      <div className="flex h-full flex-col items-center justify-center overflow-hidden bg-paper">
        <LoadingAnimation fullScreen={false} />
      </div>
    );
  }

  if (!settings) {
    return (
      <div className="flex h-full flex-col overflow-hidden bg-paper">
        <main className="flex min-h-0 flex-1 items-center justify-center">
          <div>
            <p className={sectionLabelCls}>Settings unavailable</p>
            <p className="mt-phi-2 type-body-sm text-oxford/45">The settings API did not return a payload.</p>
          </div>
        </main>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col overflow-hidden bg-paper text-oxford">
      <main className="flex min-h-0 flex-1 overflow-hidden bg-paper">
        <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden bg-paper pl-phi-3 pr-phi-5 pt-phi-4 pb-phi-5 lg:pl-phi-3 lg:pr-phi-5 lg:pt-phi-5 lg:pb-phi-5">
          {/* Section nav + draft state live in the spine (setSpineOverride) — one rail. */}
          <div className="flex min-h-0 flex-1 flex-col overflow-hidden bg-paper">
            <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden lg:h-full lg:min-h-0">
              <div className="flex items-center justify-between border-b border-oxford/[0.08] px-phi-5 py-phi-4 lg:hidden">
            <div className="flex min-w-0 flex-col gap-phi-2">
              <p className={sectionLabelCls}>Fund Configuration</p>
              {unsaved ? (
                <p className="type-meta text-oxford/45">Unsaved changes</p>
              ) : null}
            </div>
              <button
                type="button"
                onClick={handleSave}
                disabled={saving}
                className="btn-aethria-solid disabled:cursor-not-allowed disabled:opacity-40"
              >
                {saving ? 'Saving…' : 'Save'}
              </button>
              </div>

              <div ref={contentScrollRef} className="min-h-0 flex-1 overflow-y-auto scroll-smooth">
            <div className="grid min-h-full xl:grid-cols-[minmax(0,1fr)_minmax(14rem,18rem)]">
              <div className="flex min-w-0 flex-col px-phi-5 py-phi-6 lg:px-phi-7">
                <header className="mb-phi-7 max-w-[54rem]">
                  <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-oxford/40">
                    Configuration · {draft.versionLabel}
                  </p>
                  <h1 className="type-display mt-phi-3 text-[clamp(28px,3vw,42px)] leading-[1.08] text-oxford">
                    How this fund thinks<span className="wordmark-dot">.</span>
                  </h1>
                  <p className="mt-phi-3 max-w-[42rem] type-body-sm leading-relaxed text-oxford/55">
                    Configure the mandate, memo output, ruling experience, and the engine settings that sit behind them.
                  </p>
                  {(status || errors.length > 0) && (
                    <div className="mt-phi-5 border-t border-oxford/[0.08] pt-phi-3" role={errors.length ? 'alert' : 'status'}>
                      {errors.length > 0 ? (
                        <ul className="flex flex-col gap-phi-1">
                          {errors.map((error) => <li key={error} className="type-body-sm text-escalation/75">{error}</li>)}
                        </ul>
                      ) : (
                        <p className="type-body-sm text-oxford/50">{status}</p>
                      )}
                    </div>
                  )}
                </header>

                <SettingsSection id="mandate" title="Fund Mandate" kicker="The operating mandate used by discovery, fund-fit language, and frontend recommendation context.">
                  <div className="grid gap-phi-5">
                    <div className="grid gap-phi-5 md:grid-cols-2">
                      <TextField id="fund-name" label="Fund name" value={draft.mandate.fundName} onChange={(value) => updateMandate('fundName', String(value))} />
                      <TextField id="mandate-name" label="Mandate name" value={draft.mandate.mandateName} onChange={(value) => updateMandate('mandateName', String(value))} />
                    </div>
                    <ChipGroup label="Preferred stages" options={stageOptions} selected={draft.mandate.preferredStages} onChange={(value) => updateMandate('preferredStages', value)} />
                    <ChipGroup label="Geographies" options={geographyOptions} selected={draft.mandate.geographies} onChange={(value) => updateMandate('geographies', value)} />
                    <TextField id="custom-geography" label="Custom geography" value={draft.mandate.customGeography} onChange={(value) => updateMandate('customGeography', String(value))} />
                    <ChipGroup label="Sectors" options={sectorOptions} selected={draft.mandate.sectors} onChange={(value) => updateMandate('sectors', value)} />
                    <div className="grid gap-phi-5 md:grid-cols-2">
                      <TextField id="custom-sectors" label="Custom sectors" value={draft.mandate.customSectors} onChange={(value) => updateMandate('customSectors', String(value))} />
                      <TextField id="excluded-sectors" label="Excluded sectors" value={draft.mandate.excludedSectors} onChange={(value) => updateMandate('excludedSectors', String(value))} />
                    </div>
                    <TextField id="business-models" label="Preferred business models" value={draft.mandate.businessModels} onChange={(value) => updateMandate('businessModels', String(value))} />
                    <div className="grid gap-phi-5 md:grid-cols-3">
                      <TextField id="check-min" label="Check size min" type="number" value={draft.mandate.checkSizeMin} onChange={(value) => updateMandate('checkSizeMin', Number(value))} min={0} />
                      <TextField id="check-max" label="Check size max" type="number" value={draft.mandate.checkSizeMax} onChange={(value) => updateMandate('checkSizeMax', Number(value))} min={0} />
                      <TextField id="ownership" label="Ownership target %" type="number" value={draft.mandate.ownershipTarget} onChange={(value) => updateMandate('ownershipTarget', Number(value))} min={0} max={100} />
                    </div>
                    <TextField id="minimum-traction" label="Minimum traction expectations" value={draft.mandate.minimumTraction} onChange={(value) => updateMandate('minimumTraction', String(value))} />
                    <TextAreaField id="thesis-text" label="Notes / thesis text" rows={7} value={draft.mandate.thesisText} onChange={(value) => updateMandate('thesisText', value)} />
                    <div className="flex flex-wrap items-center gap-phi-4 border-t border-oxford/[0.06] pt-phi-4">
                      <button type="button" onClick={publishThesis} disabled={thesisBusy || thesisPublishDisabledReason != null} className={actionBtnCls}>
                        {thesisBusy ? 'Publishing...' : 'Publish fund thesis version'}
                      </button>
                      <p className="type-meta text-oxford/[0.38]">
                        {thesisPublishDisabledReason ?? (thesisSummary ? `Active thesis v${thesisSummary.active_version_number}` : 'No active thesis loaded')}
                      </p>
                    </div>
                  </div>
                </SettingsSection>

                <SettingsSection id="budget" title="Operations" kicker="Control which agents run and how often the pipeline checks for new work. No hidden runtime limits." className="order-5">
                  <div className="grid gap-phi-5 md:grid-cols-2">
                    <div className="flex flex-col gap-phi-2">
                      <label htmlFor="risk-sensitivity" className={labelCls}>Escalation sensitivity</label>
                      <select id="risk-sensitivity" value={draft.risk.sensitivity} onChange={(event) => updateRisk('sensitivity', event.target.value as RiskSensitivity)} className={selectCls} style={selectStyle}>
                        <option value="conservative">Conservative</option>
                        <option value="balanced">Balanced</option>
                        <option value="aggressive">Aggressive</option>
                      </select>
                    </div>
                    <ToggleRow id="scouts-enabled" checked={settings.agent_config.scouts_enabled} onChange={(value) => setSettings((current) => current ? { ...current, agent_config: { ...current.agent_config, scouts_enabled: value } } : current)} label="Scouts enabled" />
                    <ToggleRow id="reviewers-enabled" checked={settings.agent_config.reviewers_enabled} onChange={(value) => setSettings((current) => current ? { ...current, agent_config: { ...current.agent_config, reviewers_enabled: value } } : current)} label="Reviewers enabled" />
                    <ToggleRow id="partners-enabled" checked={settings.agent_config.partners_enabled} onChange={(value) => setSettings((current) => current ? { ...current, agent_config: { ...current.agent_config, partners_enabled: value } } : current)} label="Partners enabled" />
                    <ToggleRow id="budget-enabled" checked={settings.cost_budget.enabled} onChange={(value) => setSettings((current) => current ? { ...current, cost_budget: { ...current.cost_budget, enabled: value } } : current)} label="Cost budget enabled" />
                  </div>
                </SettingsSection>

                <SettingsSection id="weights" title="Scoring Weights" kicker="Set how much each reviewer dimension contributes to the overall score. The total stays balanced at 100%." className="order-6">
                  <div className="flex flex-col gap-phi-4">
                    <div className="flex flex-wrap items-baseline justify-between gap-phi-4 border-b border-oxford/[0.06] pb-phi-4">
                      <div className="flex items-baseline gap-phi-3">
                        <p className={`font-mono text-[1.6rem] tabular-nums ${weightValidation.valid ? 'text-oxford' : 'text-escalation/75'}`}>{weightValidation.total}%</p>
                        <p className="type-meta text-oxford/40">Total weight</p>
                      </div>
                      <p className="type-meta text-oxford/40">Adjust one — the rest rebalance to 100</p>
                    </div>
                    {draft.scoringWeights.map((item) => (
                      <div key={item.key} className="grid gap-phi-3 border-b border-oxford/[0.055] py-phi-4 md:grid-cols-[minmax(150px,22%)_minmax(0,1fr)_92px] md:items-start">
                        <div>
                          <p className="type-body-emphasis text-oxford">{item.label}</p>
                          <p className="mt-phi-1 type-meta leading-snug text-oxford/40">{item.description}</p>
                        </div>
                        <p className="type-body-sm leading-relaxed text-oxford/50">{getWeightImpactText(item.key)}</p>
                        <input
                          type="number"
                          min={0}
                          max={100}
                          value={item.weight}
                          onChange={(event) => updateDraft((current) => ({
                            ...current,
                            scoringWeights: rebalanceWeights(current.scoringWeights, item.key, Number(event.target.value)),
                          }))}
                          className={`${inputCls} text-right font-mono tabular-nums`}
                          aria-label={`${item.label} weight`}
                        />
                      </div>
                    ))}

                    <div className="mt-phi-2 border-t border-oxford/[0.08] pt-phi-4">
                      <div className="flex flex-wrap items-baseline justify-between gap-phi-3">
                        <div>
                          <p className={labelCls}>Active policy</p>
                          <p className="mt-phi-1 type-body-sm text-oxford/60">{draft.activePolicyVersionId ?? 'No published policy'}</p>
                        </div>
                        <p className={`type-meta ${policyUnpublished ? 'text-escalation/70' : 'text-oxford/40'}`}>
                          {policyUnpublished ? 'Unpublished changes — preview differs from published policy' : 'Published policy is up to date'}
                        </p>
                      </div>
                      <div className="mt-phi-4 flex flex-wrap items-center gap-phi-3">
                        <button type="button" onClick={handlePreviewPolicy} disabled={policyBusy} className={actionBtnCls}>
                          {policyBusy ? 'Working...' : 'Preview policy'}
                        </button>
                        <button type="button" onClick={handlePublishPolicy} disabled={policyBusy} className={solidBtnCls}>
                          {policyBusy ? 'Publishing...' : 'Publish version'}
                        </button>
                        {draft.lastPublishedAt && (
                          <p className="type-meta text-oxford/[0.38]">Last published {formatDateTime(draft.lastPublishedAt)}</p>
                        )}
                      </div>
                    </div>
                  </div>
                </SettingsSection>

                {/* Verdict chips are typographic (one fill: INVEST) — the badge
                    colour-picker section was retired with colour-coded chips. */}
                {!bandValidation.valid && (
                  <div className="mb-phi-5 border border-escalation/25 bg-escalation/[0.035] px-phi-4 py-phi-3">
                    {bandValidation.errors.map((error) => <p key={error} className="type-body-sm text-escalation/75">{error}</p>)}
                  </div>
                )}

                <SettingsSection id="thresholds" title="Decision Thresholds" kicker="Set the score bands that turn analysis into PASS, MONITOR, or INVEST. The bar below shows the live ranges." className="order-4">
                  <DecisionThresholdsPanel draft={draft} updateDraft={updateDraft} updateThreshold={updateThreshold} />
                </SettingsSection>

                <SettingsSection id="risk" title="Ruling" kicker="Choose what needs acknowledgement before a decision is recorded." className="order-3">
                  <div className="grid gap-phi-5">
                    <div className="border-y border-oxford/[0.06]">
                      <ToggleRow id="risk-ack" checked={draft.risk.requireAcknowledgement} onChange={(value) => updateRisk('requireAcknowledgement', value)} label="Require acknowledgement before ruling" hint="High-risk pending deals need a reviewed-risk step before Commit." />
                      <ToggleRow id="risk-high-only" checked={draft.risk.onlyGateHighSeverity} onChange={(value) => updateRisk('onlyGateHighSeverity', value)} label="Only gate high severity risks" hint="Leaves medium adverse items visible without slowing the ruling." />
                    </div>
                  </div>
                </SettingsSection>

                <SettingsSection id="memo" title="Memo Output" kicker="Choose how much context and reasoning appears in new investment memos." className="order-2">
                  <div className="grid gap-phi-5">
                    <div className="grid gap-phi-5 md:grid-cols-2">
                      <div className="flex flex-col gap-phi-2">
                        <label htmlFor="memo-style" className={labelCls}>Memo style</label>
                        <select id="memo-style" value={draft.memo.style} onChange={(event) => updateMemo('style', event.target.value as MemoStyle)} className={selectCls} style={selectStyle}>
                          <option value="concise">Concise</option>
                          <option value="standard">Standard</option>
                          <option value="detailed">Detailed</option>
                        </select>
                      </div>
                      <div className="flex flex-col gap-phi-2">
                        <label htmlFor="memo-tone" className={labelCls}>Memo tone</label>
                        <select id="memo-tone" value={draft.memo.tone} onChange={(event) => updateMemo('tone', event.target.value as MemoTone)} className={selectCls} style={selectStyle}>
                          <option value="partner">Partner-facing</option>
                          <option value="analyst">Analyst-facing</option>
                        </select>
                      </div>
                    </div>
                    <div className="border-y border-oxford/[0.06]">
                      <ToggleRow id="deep-dive-collapsed" checked={draft.memo.deepDiveCollapsed} onChange={(value) => updateMemo('deepDiveCollapsed', value)} label="Show deep dive collapsed by default" />
                      <ToggleRow id="evidence-excerpts" checked={draft.memo.includeEvidenceExcerpts} onChange={(value) => updateMemo('includeEvidenceExcerpts', value)} label="Include evidence excerpts" />
                      <ToggleRow id="missing-data" checked={draft.memo.includeMissingData} onChange={(value) => updateMemo('includeMissingData', value)} label="Include missing-data section" />
                      <ToggleRow id="score-reasoning" checked={draft.memo.includeScoreReasoning} onChange={(value) => updateMemo('includeScoreReasoning', value)} label="Include score reasoning" />
                      <ToggleRow id="source-confidence" checked={draft.memo.includeSourceConfidence} onChange={(value) => updateMemo('includeSourceConfidence', value)} label="Include source confidence" />
                    </div>
                  </div>
                </SettingsSection>

              </div>

              <PreviewPanel
                config={draft}
                unsaved={unsaved}
                lastSavedAt={lastSavedAt}
                saving={saving}
                onSave={() => void handleSave()}
                onReset={handleReset}
              />
            </div>
          </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
