import { useEffect, useMemo, useRef, useState, type CSSProperties } from 'react';
import { useNavigate } from 'react-router';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import LoadingAnimation from '../components/LoadingAnimation';
import { getQueryConfig } from '../lib/queryIntent';
import { formatDateTime } from '../lib/dates';
import { useAppFrame } from '../components/AppFrame';
import { SpineNavButton } from '../components/SystemBar';
import { fetchSettings, patchSettings, publishPolicy, type Settings } from '../api/settings';
import { fetchAgentsStatus, type AgentsStatus } from '../api/agents';
import {
  fetchFundThesisSummary,
  type FundThesisSummary,
} from '../api/fundThesis';
import DecisionBadge from '../components/DecisionBadge';
import { useFundConfiguration } from '../hooks';
import DecisionThresholdsPanel from './DecisionThresholdsPanel';
import { validateDecisionThresholds } from '../lib/decisionThresholds';
import {
  applyThesisVersionMetadata,
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
  'w-full rounded-none border-0 border-b border-oxford/[0.12] bg-transparent px-0 py-phi-2 type-body-sm text-oxford outline-none transition-colors placeholder:text-oxford/45 focus:border-oxford/45';
const selectCls =
  `${inputCls} cursor-pointer appearance-none bg-no-repeat bg-[length:10px] bg-[center_right_2px] pr-7`;
const labelCls = 'type-label-section text-oxford/60';
const sectionLabelCls = 'type-label-section text-oxford/[0.72]';
const metaCls = 'type-meta text-oxford/60';
const actionBtnCls =
  'type-label-section inline-flex min-h-[36px] items-center rounded-none border-0 bg-transparent p-0 text-oxford/60 transition-colors hover:text-oxford disabled:cursor-not-allowed disabled:opacity-30 btn-interaction focus:outline-none focus-visible:ring-2 focus-visible:ring-oxford/30';

/**
 * One pending edit bucket and the pipeline stages it touches once deployed.
 * Deploy is a single transaction: PATCH /api/settings (which republishes the
 * fund thesis server-side when mandate content changed) followed by a scoring
 * policy publish (idempotent — same hash re-activates the same version).
 */
interface PendingChange {
  label: string;
  stages: string;
}

function serializeConfig(config: FundConfiguration): string {
  const rest = { ...config } as Record<string, unknown>;
  for (const key of ['lastSavedAt', 'version', 'versionLabel', 'activePolicyVersionId', 'draftPolicyHash', 'publishedPolicyHash', 'lastPublishedAt']) {
    delete rest[key];
  }
  return JSON.stringify(rest);
}

function SettingsSidebarFooter({
  pending,
  lastDeployedAt,
  deploying,
  onDeploy,
  onReset,
}: {
  pending: PendingChange[];
  lastDeployedAt?: string | null;
  deploying: boolean;
  onDeploy: () => void;
  onReset: () => void;
}) {
  const live = pending.length === 0;

  return (
    <div
      className="mt-phi-6 min-w-0 shrink-0 border-t border-oxford/[0.075] pt-phi-4"
      aria-label="Deployment status"
    >
      <div className="flex items-center justify-between gap-phi-2">
        <span className="font-mono text-[12px] uppercase tracking-[0.12em] text-oxford/60">{live ? 'Live' : 'Draft'}</span>
        <span
          className={`inline-flex shrink-0 items-center gap-phi-2 font-mono text-[12px] uppercase tracking-[0.10em] transition-colors ${live ? 'text-oxford/60' : 'text-escalation/80'}`}
          aria-live="polite"
        >
          <span
            className={`h-1.5 w-1.5 shrink-0 rounded-none signal-dot-breathe transition-colors ${live ? 'bg-oxford' : 'bg-escalation/70'}`}
            aria-hidden
          />
          {live ? 'Deployed' : `${pending.length} pending`}
        </span>
      </div>
      {live ? (
        <p className="mt-phi-2 truncate type-body-sm leading-snug text-oxford/60">
          {lastDeployedAt ? `Live · deployed ${formatSettingsSavedAt(lastDeployedAt)}` : 'Deploy to put this configuration live'}
        </p>
      ) : (
        <ul className="mt-phi-2 flex flex-col gap-phi-1" aria-label="Pending changes">
          {pending.map((item) => (
            <li key={item.label} className="flex items-baseline justify-between gap-phi-3 type-meta">
              <span className="shrink-0 text-oxford">{item.label}</span>
              <span className="text-right text-oxford/60">{item.stages}</span>
            </li>
          ))}
        </ul>
      )}
      <div className="mt-phi-4 flex flex-col gap-phi-2">
        <button
          type="button"
          onClick={onDeploy}
          disabled={deploying || live}
          className="w-full btn-aethria-solid disabled:cursor-not-allowed disabled:opacity-40"
        >
          {deploying ? 'Deploying…' : 'Deploy changes'}
        </button>
        <button
          type="button"
          onClick={onReset}
          disabled={deploying}
          className={`${actionBtnCls} w-full justify-center`}
          title="Restore local defaults; deploy to make them live"
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
        className={`${inputCls} disabled:cursor-not-allowed disabled:text-oxford/60 disabled:opacity-60`}
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
        className="w-full resize-y rounded-none border border-oxford/[0.08] bg-oxford/[0.025] px-phi-3 py-phi-3 type-body-sm leading-relaxed text-oxford outline-none transition-colors placeholder:text-oxford/45 focus:border-oxford/[0.28]"
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
        {hint && <p className="mt-phi-1 type-meta leading-snug text-oxford/60">{hint}</p>}
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
              className={`type-meta inline-flex min-h-[36px] items-center justify-center rounded-none px-phi-3 transition-colors ${active ? 'bg-oxford text-paper' : 'bg-oxford/[0.045] text-oxford/60 hover:bg-oxford/[0.075]'}`}
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
          <p className="mt-phi-3 max-w-[17rem] type-body-sm leading-relaxed text-oxford/60">{kicker}</p>
        </div>
        <div className="min-w-0">{children}</div>
      </div>
    </section>
  );
}

function PreviewPanel({
  config,
  pending,
  lastDeployedAt,
  deploying,
  onDeploy,
  onReset,
}: {
  config: FundConfiguration;
  pending: PendingChange[];
  lastDeployedAt?: string | null;
  deploying: boolean;
  onDeploy: () => void;
  onReset: () => void;
}) {
  const weightTotal = validateWeights(config.scoringWeights).total;
  return (
    <aside className="relative hidden min-h-full shrink-0 self-stretch border-l border-oxford/[0.08] xl:block">
      <div className="sticky top-0 z-[1] flex max-h-[calc(100dvh)] flex-col overflow-y-auto bg-paper px-phi-5 pt-phi-6 pb-phi-6">
        <p className="type-label-section text-oxford/60">Configuration Preview</p>
        <div className="mt-phi-4 flex flex-col gap-phi-5">
          <div>
            <p className="type-meta text-oxford/60">Mandate</p>
            <p className="mt-phi-2 type-body-emphasis text-oxford">{config.mandate.fundName || 'Unnamed fund'}</p>
            <p className="mt-phi-1 type-body-sm text-oxford/60">
              {[...config.mandate.preferredStages, ...config.mandate.geographies].filter(Boolean).join(' · ') || 'No mandate scope set'}
            </p>
          </div>
          <div className="border-t border-oxford/[0.06] pt-phi-4">
            <p className="type-meta text-oxford/60">Total scoring weight</p>
            <p className={`mt-phi-2 font-mono text-[1.65rem] tabular-nums ${weightTotal === 100 ? 'text-oxford' : 'text-escalation/75'}`}>{weightTotal}%</p>
          </div>
          <div className="border-t border-oxford/[0.06] pt-phi-4">
            <p className="type-meta text-oxford/60">Verdict marks</p>
            <div className="mt-phi-3 flex flex-wrap gap-phi-2">
              {(['INVEST', 'MONITOR', 'PASS'] as const).map((id) => (
                <DecisionBadge key={id} variant={id} />
              ))}
            </div>
          </div>
          <div className="border-t border-oxford/[0.06] pt-phi-4">
            <p className="type-meta text-oxford/60">Score cutoffs</p>
            <div className="mt-phi-3 flex flex-col gap-phi-2">
              {config.scoreBands.map((item) => (
                <p key={item.id} className="type-meta text-oxford/60">
                  <span className="font-mono tabular-nums">{item.min}–{item.max}</span> {item.label}
                </p>
              ))}
              <p className="type-meta text-oxford/60">
                Stale after {config.thresholds.staleAfterHours}h · confidence ≥ {config.thresholds.confidenceFloor}
              </p>
            </div>
          </div>
          <div className="border-t border-oxford/[0.06] pt-phi-4">
            <p className="type-meta text-oxford/60">Risk gating</p>
            <p className="mt-phi-2 type-body-sm text-oxford/60">
              {config.risk.requireAcknowledgement ? `${config.risk.sensitivity} sensitivity` : 'Acknowledgement disabled'}
            </p>
          </div>
        </div>
        <SettingsSidebarFooter
          pending={pending}
          lastDeployedAt={lastDeployedAt}
          deploying={deploying}
          onDeploy={onDeploy}
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

  // Draft vs Live: pending edit buckets and the pipeline stages each touches.
  const operationsDirty = serializeOperations(settings) !== savedOperationsSnapshot;
  const pendingChanges = useMemo<PendingChange[]>(() => {
    const items: PendingChange[] = [];
    let saved: Partial<FundConfiguration> | null = null;
    try {
      saved = savedSnapshot ? (JSON.parse(savedSnapshot) as Partial<FundConfiguration>) : null;
    } catch {
      saved = null;
    }
    const differs = (a: unknown, b: unknown) => JSON.stringify(a) !== JSON.stringify(b);
    if (saved) {
      if (differs(draft.mandate, saved.mandate)) {
        items.push({ label: 'Mandate', stages: 'Scout · Reviewer' });
      }
      if (
        differs(draft.scoringWeights, saved.scoringWeights)
        || differs(draft.scoreBands, saved.scoreBands)
        || differs(draft.thresholds, saved.thresholds)
      ) {
        items.push({ label: 'Scoring', stages: 'Reviewer · Partner' });
      }
      if (differs(draft.risk, saved.risk)) items.push({ label: 'Ruling', stages: 'Decision flow' });
      if (differs(draft.memo, saved.memo)) items.push({ label: 'Memo output', stages: 'Partner memos' });
      // Catch-all for config fields outside the buckets above (e.g. rubric).
      if (!items.length && serializeConfig(draft) !== savedSnapshot) {
        items.push({ label: 'Configuration', stages: 'Pipeline' });
      }
    }
    if (operationsDirty) items.push({ label: 'Operations', stages: 'Pipeline runtime' });
    if (!draft.activePolicyVersionId) {
      items.push({ label: 'Scoring policy', stages: 'Never published' });
    }
    return items;
  }, [draft, savedSnapshot, operationsDirty]);
  const unsaved = pendingChanges.length > 0;
  const storageNotReady = agentsStatus != null && !agentsStatus.supabase_configured;

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

  // One explicit deployment transaction. Both backend steps are idempotent
  // (thesis sync dedupes on unchanged content; policy publish dedupes by hash),
  // so the whole sequence can run unconditionally and re-running converges.
  const handleDeploy = async () => {
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

    // Step 1 — persist settings; the backend republishes the fund thesis
    // when mandate content changed (no-op otherwise).
    const mapped = mapFundConfigToSettings(draft, settings);
    const result = await patchSettings(mapped);
    if (result.error) {
      setSaving(false);
      setErrors(result.error.errors.length ? result.error.errors : [result.error.message]);
      return;
    }

    // Step 2 — publish the scoring policy from what was just saved.
    const policyResult = await publishPolicy(result.data?.fund_config ?? draft);
    const policyError = policyResult.error
      ? (policyResult.error.errors.length ? policyResult.error.errors.join(' ') : policyResult.error.message)
      : null;

    // Step 3 — reconcile local state with what is now live (policy publish
    // rewrites fund_config pointers server-side, so refetch is the authority).
    const refreshed = await fetchSettings().catch(() => null);
    const summary = await fetchFundThesisSummary().catch(() => null);
    const liveSettings = refreshed ?? result.data ?? settings;
    setSettings(liveSettings);
    setSavedOperationsSnapshot(serializeOperations(liveSettings));
    let liveConfig = liveSettings.fund_config ?? draft;
    if (summary?.active_version_number != null) {
      setThesisSummary(summary);
      liveConfig = applyThesisVersionMetadata(liveConfig, summary.active_version_number);
    }
    const saved = saveLocalConfiguration(liveConfig);
    setConfiguration(saved);
    setDraft(saved);
    setSavedSnapshot(serializeConfig(saved));
    await queryClient.invalidateQueries({ queryKey: ['settings'] });
    await queryClient.invalidateQueries({ queryKey: ['fund-thesis'] });

    if (policyError) {
      setErrors([`Settings and fund thesis are live, but the scoring policy did not publish: ${policyError}`]);
    } else {
      const thesisPart = summary?.active_version_number != null
        ? ` · ${thesisVersionLabel(summary.active_version_number)}`
        : '';
      const policyPart = policyResult.policy ? ` · policy ${policyResult.policy.policy_version_id}` : '';
      setStatus(`Deployed — configuration is live${thesisPart}${policyPart}.`);
    }
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
  // Handlers (and the pending list) are reached through refs so the projection
  // effect re-runs only when displayed values change, never on identity.
  const lastDeployedAt = draft.lastPublishedAt ?? draft.lastSavedAt;
  const spineActionsRef = useRef({ deploy: () => {}, reset: () => {} });
  spineActionsRef.current = { deploy: () => void handleDeploy(), reset: handleReset };
  const pendingRef = useRef<PendingChange[]>(pendingChanges);
  pendingRef.current = pendingChanges;
  const pendingKey = pendingChanges.map((item) => item.label).join('|');

  useEffect(() => {
    const scrollToSection = (id: SectionId) => {
      setActiveSection(id);
      const target = contentScrollRef.current?.querySelector<HTMLElement>(`#${id}`);
      target?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    };
    const pending = pendingRef.current;
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
          <p className="px-2 pb-phi-1 pt-phi-4 font-mono text-[12px] uppercase tracking-[0.12em] text-white/60">
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
        <section aria-label="Deployment status" className="border-t border-white/[0.07] px-2 pt-phi-3">
          <div className="flex items-center justify-between gap-phi-2">
            <span className="font-mono text-[12px] uppercase tracking-[0.12em] text-white/60">{unsaved ? 'Draft' : 'Live'}</span>
            <span
              className={`inline-flex shrink-0 items-center gap-phi-2 font-mono text-[12px] uppercase tracking-[0.10em] ${
                unsaved ? 'text-escalation-bright/90' : 'text-white/60'
              }`}
              aria-live="polite"
            >
              <span
                className={`h-1.5 w-1.5 shrink-0 rounded-none ${unsaved ? 'bg-escalation-bright/80' : 'bg-white/55'}`}
                aria-hidden
              />
              {unsaved ? `${pending.length} pending` : 'Deployed'}
            </span>
          </div>
          {unsaved ? (
            <ul className="mt-phi-2 flex flex-col gap-phi-1" aria-label="Pending changes">
              {pending.map((item) => (
                <li key={item.label} className="flex items-baseline justify-between gap-phi-3 font-sans text-[12px] leading-snug">
                  <span className="shrink-0 text-white/85">{item.label}</span>
                  <span className="text-right text-white/60">{item.stages}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-phi-2 truncate font-sans text-[12px] leading-snug text-white/60">
              {lastDeployedAt ? `Live · deployed ${formatSettingsSavedAt(lastDeployedAt)}` : 'Deploy to put configuration live'}
            </p>
          )}
          <div className="mt-phi-3 flex flex-col gap-phi-2 xl:hidden">
            <button
              type="button"
              onClick={() => spineActionsRef.current.deploy()}
              disabled={saving || !unsaved}
              className="w-full btn-aethria-solid !bg-paper !text-oxford disabled:cursor-not-allowed disabled:opacity-40"
            >
              {saving ? 'Deploying…' : 'Deploy changes'}
            </button>
            <button
              type="button"
              onClick={() => spineActionsRef.current.reset()}
              disabled={saving}
              className="inline-flex min-h-[32px] w-full items-center justify-center font-mono text-[12px] uppercase tracking-[0.12em] text-white/60 transition-colors hover:text-white/80 disabled:opacity-50 btn-interaction"
              title="Restore local defaults; deploy to make them live"
            >
              Reset to defaults
            </button>
          </div>
        </section>
      ),
    });
  }, [setSpineOverride, navigate, activeSection, unsaved, saving, lastDeployedAt, pendingKey]);

  // Leaving the room returns the spine to the workspaces.
  useEffect(() => () => setSpineOverride(null), [setSpineOverride]);

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
            <p className="mt-phi-2 type-body-sm text-oxford/60">The settings API did not return a payload.</p>
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
                <p className="type-meta text-oxford/60">{pendingChanges.length} pending — not yet live</p>
              ) : null}
            </div>
              <button
                type="button"
                onClick={handleDeploy}
                disabled={saving || !unsaved}
                className="btn-aethria-solid disabled:cursor-not-allowed disabled:opacity-40"
              >
                {saving ? 'Deploying…' : 'Deploy'}
              </button>
              </div>

              <div ref={contentScrollRef} className="min-h-0 flex-1 overflow-y-auto scroll-smooth">
            <div className="grid min-h-full xl:grid-cols-[minmax(0,1fr)_minmax(14rem,18rem)]">
              <div className="flex min-w-0 flex-col px-phi-5 py-phi-6 lg:px-phi-7">
                <header className="mb-phi-7 max-w-[54rem]">
                  <p className="font-mono text-[12px] uppercase tracking-[0.16em] text-oxford/60">
                    Configuration · {draft.versionLabel}
                  </p>
                  <h1 className="type-display mt-phi-3 text-[clamp(28px,3vw,42px)] leading-[1.08] text-oxford">
                    How this fund thinks<span className="wordmark-dot">.</span>
                  </h1>
                  <p className="mt-phi-3 max-w-[42rem] type-body-sm leading-relaxed text-oxford/60">
                    Configure the mandate, memo output, ruling experience, and the engine settings that sit behind them.
                    Edits stay in draft until you deploy — one action puts the settings, fund thesis, and scoring policy live.
                  </p>
                  {(status || errors.length > 0) && (
                    <div className="mt-phi-5 border-t border-oxford/[0.08] pt-phi-3" role={errors.length ? 'alert' : 'status'}>
                      {errors.length > 0 ? (
                        <ul className="flex flex-col gap-phi-1">
                          {errors.map((error) => <li key={error} className="type-body-sm text-escalation/75">{error}</li>)}
                        </ul>
                      ) : (
                        <p className="type-body-sm text-oxford/60">{status}</p>
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
                    <div className="border-t border-oxford/[0.06] pt-phi-4">
                      <p className="type-meta text-oxford/60">
                        {storageNotReady
                          ? 'Supabase storage is required to version the fund thesis.'
                          : thesisSummary
                            ? `Live: Fund Thesis v${thesisSummary.active_version_number}. Deploying a mandate change publishes the next version automatically.`
                            : 'No active thesis yet — deploying the mandate publishes v1.'}
                      </p>
                    </div>
                  </div>
                </SettingsSection>

                <SettingsSection id="memo" title="Memo Output" kicker="Choose how much context and reasoning appears in new investment memos.">
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

                <SettingsSection id="risk" title="Ruling" kicker="Choose what needs acknowledgement before a decision is recorded.">
                  <div className="grid gap-phi-5">
                    <div className="border-y border-oxford/[0.06]">
                      <ToggleRow id="risk-ack" checked={draft.risk.requireAcknowledgement} onChange={(value) => updateRisk('requireAcknowledgement', value)} label="Require acknowledgement before ruling" hint="High-risk pending deals need a reviewed-risk step before Commit." />
                      <ToggleRow id="risk-high-only" checked={draft.risk.onlyGateHighSeverity} onChange={(value) => updateRisk('onlyGateHighSeverity', value)} label="Only gate high severity risks" hint="Leaves medium adverse items visible without slowing the ruling." />
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

                <SettingsSection id="thresholds" title="Decision Thresholds" kicker="Set the score bands that turn analysis into PASS, MONITOR, or INVEST. The bar below shows the live ranges.">
                  <DecisionThresholdsPanel draft={draft} updateDraft={updateDraft} updateThreshold={updateThreshold} />
                </SettingsSection>

                <SettingsSection id="budget" title="Operations" kicker="Control which agents run and how often the pipeline checks for new work. No hidden runtime limits.">
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

                <SettingsSection id="weights" title="Scoring Weights" kicker="Set how much each reviewer dimension contributes to the overall score. The total stays balanced at 100%.">
                  <div className="flex flex-col gap-phi-4">
                    <div className="flex flex-wrap items-baseline justify-between gap-phi-4 border-b border-oxford/[0.06] pb-phi-4">
                      <div className="flex items-baseline gap-phi-3">
                        <p className={`font-mono text-[1.6rem] tabular-nums ${weightValidation.valid ? 'text-oxford' : 'text-escalation/75'}`}>{weightValidation.total}%</p>
                        <p className="type-meta text-oxford/60">Total weight</p>
                      </div>
                      <p className="type-meta text-oxford/60">Adjust one — the rest rebalance to 100</p>
                    </div>
                    {draft.scoringWeights.map((item) => (
                      <div key={item.key} className="grid gap-phi-3 border-b border-oxford/[0.055] py-phi-4 md:grid-cols-[minmax(150px,22%)_minmax(0,1fr)_92px] md:items-start">
                        <div>
                          <p className="type-body-emphasis text-oxford">{item.label}</p>
                          <p className="mt-phi-1 type-meta leading-snug text-oxford/60">{item.description}</p>
                        </div>
                        <p className="type-body-sm leading-relaxed text-oxford/60">{getWeightImpactText(item.key)}</p>
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
                          <p className={labelCls}>Live scoring policy</p>
                          <p className="mt-phi-1 type-body-sm text-oxford/60">{draft.activePolicyVersionId ?? 'No published policy'}</p>
                        </div>
                        <p className="type-meta text-oxford/60">
                          {draft.lastPublishedAt
                            ? `Last published ${formatDateTime(draft.lastPublishedAt)}`
                            : 'Published on first deploy'}
                        </p>
                      </div>
                      <p className="mt-phi-3 type-meta text-oxford/60">
                        Deploying a scoring change publishes the next policy version automatically. New reviews use the live version.
                      </p>
                    </div>
                  </div>
                </SettingsSection>

              </div>

              <PreviewPanel
                config={draft}
                pending={pendingChanges}
                lastDeployedAt={lastDeployedAt}
                deploying={saving}
                onDeploy={() => void handleDeploy()}
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
