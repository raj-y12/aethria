import { useEffect, useMemo, useRef, useState, type CSSProperties } from 'react';
import { useNavigate } from 'react-router';
import { useQueryClient } from '@tanstack/react-query';
import LoadingAnimation from '../components/LoadingAnimation';
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
  CANONICAL_DIMENSIONS,
  CANONICAL_DIMENSION_KEYS,
  DIMENSION_SCORE_BANDS,
  UNIVERSAL_SCORE_BANDS,
  applyThesisVersionMetadata,
  buildFundConfigThesisPayload,
  clearFundConfiguration,
  getWeightImpactText,
  mapFundConfigToSettings,
  thesisVersionLabel,
  rebalanceWeights,
  validateScoreBands,
  validateWeights,
  type CoreDimensionKey,
  type FundConfiguration,
  type MemoStyle,
  type MemoTone,
  type RiskSensitivity,
} from '../lib/fundConfiguration';

type SectionId =
  | 'mandate'
  | 'weights'
  | 'bands'
  | 'thresholds'
  | 'risk'
  | 'memo'
  | 'rubric'
  | 'budget';

const SELECT_CHEVRON =
  "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='10' viewBox='0 0 10 10'%3E%3Cpath fill='%231a2b48' fill-opacity='0.45' d='M0 3h10L5 8z'/%3E%3C/svg%3E\")";

const selectStyle: CSSProperties = { backgroundImage: SELECT_CHEVRON };

const sections: Array<{ id: SectionId; label: string; short: string }> = [
  { id: 'mandate', label: 'Fund Mandate', short: 'Mandate' },
  { id: 'budget', label: 'Operations', short: 'Ops' },
  { id: 'weights', label: 'Scoring Weights', short: 'Weights' },
  { id: 'thresholds', label: 'Decision Thresholds', short: 'Thresholds' },
  { id: 'risk', label: 'Adverse / Risk', short: 'Risk' },
  { id: 'memo', label: 'Memo Output', short: 'Memo' },
  { id: 'rubric', label: 'Rubric Criteria', short: 'Rubric' },
];

const stageOptions = ['Pre-seed', 'Seed', 'Series A', 'Series B+'];
const geographyOptions = ['US', 'Europe', 'UK/Ireland', 'Global'];
const sectorOptions = ['B2B SaaS', 'AI', 'Infrastructure', 'Fintech', 'Healthcare', 'Devtools', 'Climate'];
const inputCls =
  'w-full rounded-none border-0 border-b border-oxford/[0.12] bg-transparent px-0 py-phi-2 type-body-sm text-oxford outline-none transition-colors placeholder:text-oxford/25 focus:border-oxford/45';
const selectCls =
  `${inputCls} cursor-pointer appearance-none bg-no-repeat bg-[length:10px] bg-[center_right_2px] pr-7`;
const labelCls = 'type-label-section text-oxford/45';
const sectionLabelCls = 'type-label-section text-oxford/72';
const metaCls = 'type-meta text-oxford/42';
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

function serializeOperations(settings: Settings | null): string {
  if (!settings) return '';
  return JSON.stringify({
    agent_config: settings.agent_config,
    cost_budget: settings.cost_budget,
  });
}

function formatSettingsSavedAt(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return 'Saved';
  return new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  }).format(date);
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
        className="w-full resize-y rounded-none border border-oxford/[0.08] bg-oxford/[0.025] px-phi-3 py-phi-3 type-body-sm leading-relaxed text-oxford outline-none transition-colors placeholder:text-oxford/25 focus:border-oxford/28"
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
        {hint && <p className="mt-phi-1 type-meta leading-snug text-oxford/38">{hint}</p>}
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
              className={`type-meta inline-flex min-h-[30px] items-center justify-center rounded-none border px-phi-4 transition-colors btn-interaction btn-interaction--no-press focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-oxford/30 ${
                active
                  ? 'border-oxford bg-oxford/[0.04] font-semibold text-oxford'
                  : 'border-oxford/[0.14] bg-transparent text-oxford/50 hover:border-oxford/35 hover:text-oxford/75'
              }`}
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
}: {
  id: SectionId;
  title: string;
  kicker: string;
  children: React.ReactNode;
}) {
  return (
    <section id={id} className="border-t border-oxford/[0.075] py-phi-7 first:border-t-0 first:pt-0">
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

function PreviewPanel({ config }: { config: FundConfiguration }) {
  const weightTotal = validateWeights(config.scoringWeights).total;
  return (
    <aside className="relative hidden min-h-full shrink-0 self-stretch border-l border-oxford/[0.08] xl:block">
      <div className="sticky top-0 z-[1] flex max-h-[calc(100dvh)] flex-col overflow-y-auto bg-paper px-phi-5 pt-phi-6 pb-phi-6">
        <p className="type-label-section text-oxford/55">Configuration Preview</p>
        <div className="mt-phi-4 flex flex-col gap-phi-5">
          <div>
            <p className="type-meta text-oxford/35">Mandate</p>
            <p className="mt-phi-2 type-body-emphasis text-oxford">{config.mandate.fundName || 'Unnamed fund'}</p>
            <p className="mt-phi-1 type-body-sm text-oxford/52">
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
                <p key={item.id} className="type-meta text-oxford/52">
                  <span className="font-mono tabular-nums">{item.min}–{item.max}</span> {item.label}
                </p>
              ))}
              <p className="type-meta text-oxford/38">
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
          <div className="border-t border-oxford/[0.06] pt-phi-4">
            <p className="type-meta text-oxford/35">Sample outcome</p>
            <p className="mt-phi-2 type-body-emphasis text-oxford">Verdict display settings</p>
            <p className="mt-phi-1 type-body-sm text-oxford/55">
              Percentage bands shape configured score language in the app. Verdict marks are
              typographic — INVEST is the only filled chip.
            </p>
          </div>
        </div>
      </div>
    </aside>
  );
}

export default function SettingsPage() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const { setSpineOverride } = useAppFrame();

  const [settings, setSettings] = useState<Settings | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
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

  useEffect(() => {
    let cancelled = false;
    fetchSettings()
      .then((data) => {
        if (cancelled) return;
        setSettings(data);
        setSavedOperationsSnapshot(serializeOperations(data));
        setLoadError(null);
      })
      .catch((error: unknown) => {
        if (!cancelled) setLoadError(error instanceof Error ? error.message : 'Failed to load settings');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
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
  const spineActionsRef = useRef({ save: () => {}, reset: () => {} });
  spineActionsRef.current = { save: () => void handleSave(), reset: handleReset };
  const lastSavedAt = draft.lastSavedAt;

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
            surface="oxford"
            onClick={() => navigate('/v1')}
          />
          <p className="px-2 pb-phi-1 pt-phi-4 font-mono text-[10px] uppercase tracking-[0.12em] text-white/38">
            Configuration
          </p>
          {sections.map((section) => (
            <SpineNavButton
              key={section.id}
              label={section.label}
              active={activeSection === section.id}
              ariaPressed={activeSection === section.id}
              surface="oxford"
              onClick={() => scrollToSection(section.id)}
            />
          ))}
        </>
      ),
      footer: (
        <section aria-label="Draft status" className="border-t border-white/[0.07] px-2 pt-phi-3">
          <div className="flex items-center justify-between gap-phi-2">
            <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-white/38">Draft</span>
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
          <div className="mt-phi-3 flex flex-col gap-phi-2">
            <button
              type="button"
              onClick={() => spineActionsRef.current.save()}
              disabled={saving || !unsaved}
              className={
                unsaved && !saving
                  ? 'inline-flex h-9 w-full items-center justify-center rounded-none bg-paper font-mono text-[11px] uppercase tracking-[0.12em] text-oxford transition-opacity hover:opacity-90 btn-interaction'
                  : 'inline-flex h-9 w-full cursor-not-allowed items-center justify-center rounded-none border border-white/[0.18] bg-transparent font-mono text-[11px] uppercase tracking-[0.12em] text-white/35'
              }
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

  if (loading) return <LoadingAnimation />;

  if (!settings) {
    return (
      <div className="flex h-full flex-col overflow-hidden bg-paper">
        <main className="flex min-h-0 flex-1 items-center justify-center">
          <div>
            <p className={sectionLabelCls}>Settings unavailable</p>
            <p className="mt-phi-2 type-body-sm text-oxford/45">{loadError ?? 'The settings API did not return a payload.'}</p>
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
              <div className="min-w-0 px-phi-5 py-phi-6 lg:px-phi-7">
                <header className="mb-phi-7 max-w-[54rem]">
                  <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-oxford/40">
                    Configuration · {draft.versionLabel}
                  </p>
                  <h1 className="type-display mt-phi-3 text-[clamp(28px,3vw,42px)] leading-[1.08] text-oxford">
                    How this fund thinks<span className="wordmark-dot">.</span>
                  </h1>
                  <p className="mt-phi-3 max-w-[42rem] type-body-sm leading-relaxed text-oxford/55">
                    Configure mandate, backend core scoring weights, runtime limits, and the app-level ruling and memo experience. Controls marked as display-only are saved for the interface but do not override reviewer or partner policy files.
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
                      <p className="type-meta text-oxford/38">
                        {thesisPublishDisabledReason ?? (thesisSummary ? `Active thesis v${thesisSummary.active_version_number}` : 'No active thesis loaded')}
                      </p>
                    </div>
                  </div>
                </SettingsSection>

                <SettingsSection id="budget" title="Operations" kicker="Runtime gates for background pipeline cycles. Company limits cap scout, reviewer, and partner batch size; budget settings drive CostController when enabled.">
                  <div className="grid gap-phi-5 md:grid-cols-2">
                    <ToggleRow id="scouts-enabled" checked={settings.agent_config.scouts_enabled} onChange={(value) => setSettings((current) => current ? { ...current, agent_config: { ...current.agent_config, scouts_enabled: value } } : current)} label="Scouts enabled" />
                    <ToggleRow id="reviewers-enabled" checked={settings.agent_config.reviewers_enabled} onChange={(value) => setSettings((current) => current ? { ...current, agent_config: { ...current.agent_config, reviewers_enabled: value } } : current)} label="Reviewers enabled" />
                    <ToggleRow id="partners-enabled" checked={settings.agent_config.partners_enabled} onChange={(value) => setSettings((current) => current ? { ...current, agent_config: { ...current.agent_config, partners_enabled: value } } : current)} label="Partners enabled" />
                    <ToggleRow id="budget-enabled" checked={settings.cost_budget.enabled} onChange={(value) => setSettings((current) => current ? { ...current, cost_budget: { ...current.cost_budget, enabled: value } } : current)} label="Cost budget enabled" />
                    <TextField id="max-agents" label="Companies per cycle" type="number" value={settings.agent_config.max_agents_per_run} onChange={(value) => setSettings((current) => current ? { ...current, agent_config: { ...current.agent_config, max_agents_per_run: Number(value) } } : current)} min={1} />
                    <TextField id="max-tokens" label="Token cap per day" type="number" value={settings.cost_budget.max_tokens_per_run} onChange={(value) => setSettings((current) => current ? { ...current, cost_budget: { ...current.cost_budget, max_tokens_per_run: Number(value) } } : current)} min={0} />
                    <TextField id="daily-cost" label="Daily cap (USD)" type="number" value={settings.cost_budget.daily_cost_ceiling} onChange={(value) => setSettings((current) => current ? { ...current, cost_budget: { ...current.cost_budget, daily_cost_ceiling: Number(value) } } : current)} min={0} />
                    <TextField id="cooldown-seconds" label="Agent cooldown seconds" type="number" value={settings.cost_budget.cooldown_seconds} onChange={(value) => setSettings((current) => current ? { ...current, cost_budget: { ...current.cost_budget, cooldown_seconds: Number(value) } } : current)} min={0} />
                  </div>
                </SettingsSection>

                <SettingsSection id="weights" title="Scoring Weights" kicker="Weights match the five reviewer dimensions used by deterministic backend scoring. Traction and timing remain sub-signals inside Execution and Market.">
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
                          <p className="type-meta text-oxford/38">Last published {new Date(draft.lastPublishedAt).toLocaleString()}</p>
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

                <SettingsSection id="thresholds" title="Decision Thresholds" kicker="Pass, Monitor, and Invest cutoffs — synced with Partner scoring and badge ranges.">
                  <DecisionThresholdsPanel draft={draft} updateDraft={updateDraft} updateThreshold={updateThreshold} />
                </SettingsSection>

                <SettingsSection id="risk" title="Adverse / Risk Sensitivity" kicker="Controls app-level risk acknowledgement and ruling UX. Reviewer scoring and partner policy still use backend evidence and policy rules.">
                  <div className="grid gap-phi-5">
                    <div className="grid gap-phi-5 md:grid-cols-3">
                      <div className="flex flex-col gap-phi-2">
                        <label htmlFor="risk-sensitivity" className={labelCls}>Risk sensitivity</label>
                        <select id="risk-sensitivity" value={draft.risk.sensitivity} onChange={(event) => updateRisk('sensitivity', event.target.value as RiskSensitivity)} className={selectCls} style={selectStyle}>
                          <option value="conservative">Conservative</option>
                          <option value="balanced">Balanced</option>
                          <option value="aggressive">Aggressive</option>
                        </select>
                      </div>
                    </div>
                    <div className="border-y border-oxford/[0.06]">
                      <ToggleRow id="risk-ack" checked={draft.risk.requireAcknowledgement} onChange={(value) => updateRisk('requireAcknowledgement', value)} label="Require acknowledgement before ruling" hint="High-risk pending deals need a reviewed-risk step before Commit." />
                      <ToggleRow id="risk-high-only" checked={draft.risk.onlyGateHighSeverity} onChange={(value) => updateRisk('onlyGateHighSeverity', value)} label="Only gate high severity risks" hint="Leaves medium adverse items visible without slowing the ruling." />
                    </div>
                    <div className="border-b border-oxford/[0.06] pb-phi-5">
                      <div className="flex items-center justify-between gap-phi-3">
                        <p className={labelCls}>Penalty weights</p>
                        <span className="inline-flex items-center border border-oxford/[0.12] px-phi-2 py-px font-mono text-[0.625rem] uppercase tracking-wide text-oxford/45">Display only</span>
                      </div>
                      <div className="mt-phi-4 grid gap-phi-4 sm:grid-cols-2 lg:grid-cols-4">
                        <TextField id="founder-penalty" label="Founder data" type="number" value={draft.risk.missingFounderPenalty} onChange={(value) => updateRisk('missingFounderPenalty', Number(value))} min={0} max={100} disabled />
                        <TextField id="traction-penalty" label="Traction data" type="number" value={draft.risk.missingTractionPenalty} onChange={(value) => updateRisk('missingTractionPenalty', Number(value))} min={0} max={100} disabled />
                        <TextField id="contradiction-penalty" label="Contradiction" type="number" value={draft.risk.contradictionPenalty} onChange={(value) => updateRisk('contradictionPenalty', Number(value))} min={0} max={100} disabled />
                        <TextField id="weak-source-penalty" label="Weak source" type="number" value={draft.risk.weakSourcePenalty} onChange={(value) => updateRisk('weakSourcePenalty', Number(value))} min={0} max={100} disabled />
                      </div>
                      <p className={`mt-phi-3 ${metaCls}`}>Saved for policy display only (0–100). Backend reviewers do not apply these penalties.</p>
                    </div>
                  </div>
                </SettingsSection>

                <SettingsSection id="memo" title="Memo Output" kicker="Controls app memo presentation and saved memo verbosity. Existing generated memo content is not rewritten retroactively.">
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

                <SettingsSection id="rubric" title="Evaluation Framework" kicker="Aethria's institutional scoring framework. Dimensions are fixed to ensure score consistency across all evaluations — this is read-only reference. Adjust and publish weights in Scoring Weights.">
                  <div className="flex flex-col gap-phi-5">
                    <div className="border-b border-oxford/[0.06] pb-phi-4">
                      <p className="type-body-sm leading-relaxed text-oxford/52">
                        Every startup is evaluated across five institutional dimensions. Score definitions are fixed to ensure a 7 in Market always means the same thing regardless of fund configuration. You can adjust dimension weights to reflect your fund's investment priorities.
                      </p>
                    </div>

                    <div className="border-b border-oxford/[0.06] pb-phi-5">
                      <p className={sectionLabelCls}>Score scale</p>
                      <div className="mt-phi-4 flex flex-col gap-phi-3">
                        {UNIVERSAL_SCORE_BANDS.map((band) => (
                          <div key={band.label} className="grid gap-phi-3 md:grid-cols-[100px_minmax(0,1fr)]">
                            <p className="font-mono text-[1rem] tabular-nums text-oxford/60">{band.range[0]}-{band.range[1]}</p>
                            <div>
                              <p className="type-body-emphasis text-oxford">{band.label}</p>
                              <p className="mt-phi-1 type-meta leading-snug text-oxford/45">{band.description}</p>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>

                    {CANONICAL_DIMENSION_KEYS.map((dimKey) => {
                      const dim = CANONICAL_DIMENSIONS[dimKey];
                      const bands = DIMENSION_SCORE_BANDS[dimKey];
                      return (
                        <DimensionFrameworkCard
                          key={dimKey}
                          dimensionKey={dimKey}
                          label={dim.label}
                          description={dim.description}
                          bands={bands}
                          labelCls={labelCls}
                          metaCls={metaCls}
                        />
                      );
                    })}
                  </div>
                </SettingsSection>
              </div>

              <PreviewPanel config={draft} />
            </div>
          </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}

function DimensionFrameworkCard({
  dimensionKey,
  label,
  description,
  bands,
  labelCls,
  metaCls,
}: {
  dimensionKey: CoreDimensionKey;
  label: string;
  description: string;
  bands: Record<number, string>;
  labelCls: string;
  metaCls: string;
}) {
  const [expanded, setExpanded] = useState(false);
  const anchorScores = [3, 5, 7, 9] as const;
  return (
    <div className="border-t border-oxford/[0.06] pt-phi-5 first:border-t-0 first:pt-0">
      <div className="flex items-start justify-between gap-phi-4">
        <div className="min-w-0">
          <p className="type-body-emphasis text-oxford">{label}</p>
          <p className="mt-phi-1 type-body-sm leading-relaxed text-oxford/50">{description}</p>
        </div>
        <button
          type="button"
          onClick={() => setExpanded((prev) => !prev)}
          className="type-meta shrink-0 text-oxford/40 transition-colors hover:text-oxford/65"
          aria-expanded={expanded}
        >
          {expanded ? 'Hide scale' : 'Show scale'}
        </button>
      </div>
      {expanded && (
        <div className="mt-phi-4 flex flex-col gap-phi-3 border-t border-oxford/[0.04] pt-phi-4">
          {anchorScores.map((score) => (
            <div key={`${dimensionKey}-${score}`} className="grid gap-phi-2 md:grid-cols-[48px_minmax(0,1fr)]">
              <p className="font-mono text-[0.85rem] tabular-nums text-oxford/55">{score}/10</p>
              <p className={metaCls}>{bands[score]}</p>
            </div>
          ))}
          <p className={`${labelCls} mt-phi-2`}>
            These definitions are institutional and cannot be modified per fund.
          </p>
        </div>
      )}
    </div>
  );
}
