import { useEffect, useMemo, useRef, useState, type CSSProperties } from 'react';
import { useNavigate } from 'react-router';
import { useAuth } from '@clerk/react-router';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import LoadingAnimation from '../components/LoadingAnimation';
import { workspaceLayout } from '../design-system/workspaceLayout';
import { getQueryConfig } from '../lib/queryIntent';
import { fetchSettings, patchSettings, publishPolicy, type Settings } from '../api/settings';
import { fetchAgentsStatus, type AgentsStatus } from '../api/agents';
import { fetchSystemStatus } from '../api/system';
import { fetchJobs, type DurableJob } from '../api/jobs';
import {
  fetchCalibrationState,
  fetchMetaEvalSet,
  fetchMetaInsights,
  fetchMetaPromptState,
  fetchMetaReports,
  fetchScoutWeights,
} from '../api/meta';
import {
  fetchFundThesisSummary,
  type FundThesisSummary,
} from '../api/fundThesis';
import { useFundConfiguration, usePrefersReducedMotion } from '../hooks';
import DecisionThresholdsPanel from './DecisionThresholdsPanel';
import FundThesisConfirmationModal from './FundThesisConfirmationModal';
import SettingsActionDialog from './SettingsActionDialog';
import SettingsTopBar, { type SettingsStatusTone } from './SettingsTopBar';
import SettingsMobileNav from './SettingsMobileNav';
import OperationsStrip from './OperationsStrip';
import ExecutionReadinessPanel from '../components/institutional/ExecutionReadinessPanel';
import { MetaCommandTab } from '../components/system/internals';
import { validateDecisionThresholds } from '../lib/decisionThresholds';
import {
  getDeploymentConfirmation,
  getPendingChanges,
  sectionForDeploymentError,
  serializeDecisionConfig,
  SETTINGS_SECTIONS,
  type PendingChange,
  type FundThesisChangeSet,
  type SectionId,
} from './settingsModel';

import {
  applyThesisVersionMetadata,
  createDefaultFundConfiguration,
  loadFundConfiguration,
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
import {
  clearPolicyPublishRecovery,
  getPolicyPublishRecoveryStorage,
  getPolicyPublishRecoveryStorageKey,
  loadPolicyPublishRecovery,
  savePolicyPublishRecovery,
} from './policyPublishRecovery';

const SELECT_CHEVRON =
  "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='10' viewBox='0 0 10 10'%3E%3Cpath fill='%231a2b48' fill-opacity='0.45' d='M0 3h10L5 8z'/%3E%3C/svg%3E\")";

const selectStyle: CSSProperties = { backgroundImage: SELECT_CHEVRON };

const stageOptions = ['Pre-seed', 'Seed', 'Series A', 'Series B+'];
const geographyOptions = ['US', 'Europe', 'UK/Ireland', 'Global'];
const sectorOptions = ['B2B SaaS', 'AI', 'Infrastructure', 'Fintech', 'Healthcare', 'Devtools', 'Climate'];
const inputCls =
  'w-full rounded-none border-0 border-b border-oxford/[0.12] bg-transparent px-0 py-phi-2 type-body-sm text-oxford outline-none transition-colors placeholder:text-oxford/45 focus:border-oxford/45';
const selectCls =
  `${inputCls} cursor-pointer appearance-none bg-no-repeat bg-[length:10px] bg-[center_right_2px] pr-7`;
const labelCls = 'type-label-section text-xs text-oxford/70';
const sectionLabelCls = 'type-label-section text-xs text-oxford/70';
const metaCls = 'type-meta text-xs text-oxford/70';
type SettingsDialogState = 'restore' | 'leave' | null;
type AttentionSource = 'local' | 'server';
type SettingsAttention = { section: SectionId; source: AttentionSource };
type PendingPolicyPublish = { fundConfig: FundConfiguration; storageKey: string | null };

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
    <div className="flex items-center justify-between gap-phi-5 py-phi-3">
      <div className="min-w-0">
        <label htmlFor={id} className="type-body-sm text-oxford">{label}</label>
        {hint && <p className="type-note mt-phi-1 leading-snug text-oxford/70">{hint}</p>}
      </div>
      <button
        id={id}
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={`relative h-6 w-11 shrink-0 rounded-full border transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-oxford/30 ${
          checked ? 'border-oxford/30 bg-oxford' : 'border-oxford/15 bg-oxford/[0.09]'
        }`}
      >
        <span className={`absolute top-[3px] block h-4 w-4 rounded-full shadow-sm transition-transform ${checked ? 'translate-x-[22px] bg-paper' : 'translate-x-[3px] bg-oxford/35'}`} />
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
              className={`type-action inline-flex min-h-[36px] items-center justify-center rounded-none px-phi-3 text-xs transition-colors ${active ? 'bg-oxford text-paper' : 'bg-oxford/[0.045] text-oxford/70 hover:bg-oxford/[0.075]'}`}
            >
              {option}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function RoomSection({
  id,
  title,
  label,
  description,
  children,
  className,
}: {
  id: string;
  title: string;
  label?: string;
  description?: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section
      id={id}
      tabIndex={-1}
       className={`flex min-w-0 scroll-mt-16 flex-col gap-phi-4 pb-phi-5 pt-phi-5 outline-none lg:scroll-mt-0 ${className ?? ''}`}
    >
      <div>
        <div className="flex flex-wrap items-baseline justify-between gap-x-phi-4 gap-y-phi-1">
          <h2 className={sectionLabelCls}>{title}</h2>
          {label ? <span className="type-label-section text-xs text-oxford/70">{label}</span> : null}
        </div>
        {description ? (
          <p className="mt-phi-2 max-w-[42rem] type-body-sm leading-relaxed text-oxford/70">{description}</p>
        ) : null}
      </div>
      <div className="min-w-0">{children}</div>
    </section>
  );
}

function SpecRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid gap-phi-4 py-phi-6 sm:grid-cols-[clamp(110px,18%,160px)_minmax(0,1fr)] sm:items-start sm:gap-phi-5">
      <p className="type-label-section pt-phi-2 text-xs text-oxford/70">{label}</p>
      <div className="min-w-0">{children}</div>
    </div>
  );
}

function EditorialStatus({
  label,
  value,
  detail,
  tone = 'neutral',
}: {
  label: string;
  value: string;
  detail?: string;
  tone?: 'neutral' | 'ready' | 'warning';
}) {
  const dotClass = tone === 'ready'
    ? 'bg-oxford'
    : tone === 'warning'
      ? 'bg-escalation/75'
      : 'bg-oxford/30';
  return (
    <div className="grid gap-x-phi-4 gap-y-phi-2 py-phi-4 sm:grid-cols-[minmax(6rem,32%)_minmax(0,1fr)] sm:items-baseline">
      <p className="type-label-section text-xs text-oxford/70">{label}</p>
      <p className="type-body-sm inline-flex items-center gap-phi-2 text-oxford">
        <span className={`h-1.5 w-1.5 shrink-0 ${dotClass}`} aria-hidden />
        {value}
      </p>
      {detail ? <p className="type-note leading-relaxed text-escalation/70 sm:col-start-2">{detail}</p> : null}
    </div>
  );
}

function GroupHeader({ title, description }: { title: string; description: string }) {
  return (
    <div className="group-index pb-phi-5">
      <h2 className="type-display text-[clamp(1.5rem,3vw,2.3rem)] font-medium leading-none tracking-[-0.015em] text-oxford">{title}</h2>
      <p className="mt-phi-2 max-w-[48ch] type-body-sm leading-relaxed text-oxford/70">{description}</p>
    </div>
  );
}

function SettingsGroup({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children: React.ReactNode;
}) {
  return (
    <section className="settings-gallery-section">
      <div className="focus-frame">
        <GroupHeader title={title} description={description} />
        {children}
      </div>
    </section>
  );
}

export default function SettingsPage() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const { userId } = useAuth();
  const reduceMotion = usePrefersReducedMotion();
  const requestedSection = typeof window === 'undefined'
    ? null
    : new URLSearchParams(window.location.search).get('section');
  const requestedSectionId = SETTINGS_SECTIONS.some((section) => section.id === requestedSection)
    ? requestedSection as SectionId
    : null;

  const [settings, setSettings] = useState<Settings | null>(null);
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [errors, setErrors] = useState<string[]>([]);
  const [thesisConfirmation, setThesisConfirmation] = useState<FundThesisChangeSet | null>(null);
  const [activeSection, setActiveSection] = useState<SectionId>(requestedSectionId ?? 'thesis');
  const [attention, setAttention] = useState<SettingsAttention | null>(null);
  const [pendingPolicyPublish, setPendingPolicyPublish] = useState<PendingPolicyPublish | null>(null);
  const [agentsStatus, setAgentsStatus] = useState<AgentsStatus | null>(null);
  const [thesisSummary, setThesisSummary] = useState<FundThesisSummary | null>(null);
  const [savedSnapshot, setSavedSnapshot] = useState('');
  const savedSnapshotRef = useRef(savedSnapshot);
  savedSnapshotRef.current = savedSnapshot;
  const [dialog, setDialog] = useState<SettingsDialogState>(null);
  const [preRestoreDraft, setPreRestoreDraft] = useState<FundConfiguration | null>(null);
  const contentScrollRef = useRef<HTMLDivElement | null>(null);
  const hydratedRecoveryKeyRef = useRef<string | null>(null);
  const requestedSectionHandledRef = useRef<string | null>(null);

  const { configuration, setConfiguration, save: saveLocalConfiguration } = useFundConfiguration(settings, userId);
  const [draft, setDraft] = useState<FundConfiguration>(configuration);
  const draftRef = useRef(draft);
  draftRef.current = draft;
  const attentionSection = attention?.section ?? null;

  // Settings ride the shared ['settings'] cache (also fed by useSystemData):
  // returning visitors get the page instantly instead of a loading takeover.
  const settingsQuery = useQuery({
    queryKey: ['settings'],
    queryFn: () => fetchSettings().catch(() => null),
    ...getQueryConfig('STATIC'),
    refetchOnMount: 'always',
  });
  const systemStatusQuery = useQuery({
    queryKey: ['system', 'status'],
    queryFn: fetchSystemStatus,
    ...getQueryConfig('SEMI_DYNAMIC', { pollIntervalMs: 30_000 }),
    refetchInterval: 30_000,
    retry: 1,
  });
  const recentJobsQuery = useQuery<DurableJob[]>({
    queryKey: ['jobs', 'execution-diagnostics'],
    queryFn: () => fetchJobs(['dead_letter', 'retry_wait', 'failed', 'blocked'], 12),
    ...getQueryConfig('SEMI_DYNAMIC', { pollIntervalMs: 30_000 }),
    refetchInterval: 30_000,
    retry: 1,
  });
  const governanceEnabled = activeSection === 'governance';
  const metaReportsQuery = useQuery({
    queryKey: ['meta', 'reports'],
    queryFn: fetchMetaReports,
    ...getQueryConfig('STATIC'),
    enabled: governanceEnabled,
  });
  const scoutWeightsQuery = useQuery({
    queryKey: ['meta', 'weights'],
    queryFn: fetchScoutWeights,
    ...getQueryConfig('STATIC'),
    enabled: governanceEnabled,
  });
  const calibrationQuery = useQuery({
    queryKey: ['meta', 'calibration'],
    queryFn: fetchCalibrationState,
    ...getQueryConfig('STATIC'),
    enabled: governanceEnabled,
  });
  const metaPromptStateQuery = useQuery({
    queryKey: ['meta', 'prompt-state'],
    queryFn: () => fetchMetaPromptState(),
    ...getQueryConfig('STATIC'),
    enabled: governanceEnabled,
  });
  const metaEvalSetQuery = useQuery({
    queryKey: ['meta', 'eval-set'],
    queryFn: fetchMetaEvalSet,
    ...getQueryConfig('STATIC'),
    enabled: governanceEnabled,
  });
  const metaInsightsQuery = useQuery({
    queryKey: ['meta', 'insights'],
    queryFn: fetchMetaInsights,
    ...getQueryConfig('STATIC'),
    enabled: governanceEnabled,
  });

  // Warm cache data gives an instant first paint, while the mount refetch above
  // reconciles it with the server. Incoming data may replace a clean draft, but
  // never clobbers edits the user has made since the last saved snapshot.
  const seededRef = useRef(false);
  useEffect(() => {
    const incomingSettings = settingsQuery.data;
    if (!incomingSettings) return;
    const incomingConfiguration = loadFundConfiguration(incomingSettings, userId);
    const incomingSnapshot = serializeDecisionConfig(incomingConfiguration);
    if (!seededRef.current) {
      seededRef.current = true;
      setSettings(incomingSettings);
      draftRef.current = incomingConfiguration;
      savedSnapshotRef.current = incomingSnapshot;
      setDraft(incomingConfiguration);
      setSavedSnapshot(incomingSnapshot);
      return;
    }

    setSettings(incomingSettings);
    if (serializeDecisionConfig(draftRef.current) !== savedSnapshotRef.current) return;

    setConfiguration(incomingConfiguration);
    draftRef.current = incomingConfiguration;
    savedSnapshotRef.current = incomingSnapshot;
    setDraft(incomingConfiguration);
    setSavedSnapshot(incomingSnapshot);
  }, [settingsQuery.data]);

  const loading = settings == null && settingsQuery.isPending;

  useEffect(() => {
    let cancelled = false;
    fetchAgentsStatus().then((data) => { if (!cancelled) setAgentsStatus(data ?? null); }).catch(() => undefined);
    fetchFundThesisSummary().then((data) => { if (!cancelled) setThesisSummary(data); }).catch(() => undefined);
    return () => { cancelled = true; };
  }, []);

  const recoveryStorageKey = useMemo(
    () => getPolicyPublishRecoveryStorageKey(userId, settings),
    [settings, userId],
  );

  useEffect(() => {
    if (!settings || !recoveryStorageKey || hydratedRecoveryKeyRef.current === recoveryStorageKey) return;
    const restored = loadPolicyPublishRecovery(
      getPolicyPublishRecoveryStorage(),
      recoveryStorageKey,
      settings,
    );
    hydratedRecoveryKeyRef.current = recoveryStorageKey;
    if (!restored) return;
    setPendingPolicyPublish({ fundConfig: restored, storageKey: recoveryStorageKey });
    setSavedSnapshot(serializeDecisionConfig(restored));
  }, [recoveryStorageKey, settings]);

  useEffect(() => {
    const versionNumber = thesisSummary?.active_version_number;
    if (versionNumber == null || versionNumber < 1) return;
    setConfiguration((current) => applyThesisVersionMetadata(current, versionNumber));
    setDraft((current) => applyThesisVersionMetadata(current, versionNumber));
  }, [thesisSummary?.active_version_number]);

  const weightValidation = useMemo(() => validateWeights(draft.scoringWeights), [draft.scoringWeights]);
  const bandValidation = useMemo(() => validateScoreBands(draft.scoreBands), [draft.scoreBands]);
  const thresholdValidation = useMemo(() => validateDecisionThresholds(draft), [draft]);

  useEffect(() => {
    if (attention?.source !== 'local') return;
    if (attention.section === 'weights' && weightValidation.valid) setAttention(null);
    if (
      attention.section === 'thresholds'
      && bandValidation.valid
      && thresholdValidation.valid
    ) {
      setAttention(null);
    }
  }, [attention, bandValidation.valid, thresholdValidation.valid, weightValidation.valid]);
  // Draft vs Live only covers deployable decision configuration. Runtime
  // controls save independently in OperationsStrip and never enter this list.
  const pendingChanges = useMemo<PendingChange[]>(
    () => getPendingChanges(draft, savedSnapshot),
    [draft, savedSnapshot],
  );
  const hasPendingPolicyChanges = useMemo(
    () => serializeDecisionConfig(draft) !== savedSnapshot || pendingPolicyPublish != null,
    [draft, pendingPolicyPublish, savedSnapshot],
  );
  const checkpointDraftCount = pendingPolicyPublish
    ? pendingChanges.filter((change) => change.label !== 'Scoring policy').length
    : 0;
  const checkpointMessage = checkpointDraftCount > 0
    ? `Scoring policy publish pending · ${checkpointDraftCount} newer draft ${checkpointDraftCount === 1 ? 'change' : 'changes'}`
    : 'Scoring policy publish pending';
  const topBarStatus: { message: string; tone: SettingsStatusTone } = pendingPolicyPublish
    ? {
        message: errors.length > 0 ? `${checkpointMessage} · ${errors.join(' ')}` : checkpointMessage,
        tone: errors.length > 0 ? 'error' : saving ? 'progress' : 'draft',
      }
    : saving
      ? { message: 'Deploying…', tone: 'progress' }
    : errors.length > 0
      ? { message: errors.join(' '), tone: 'error' }
      : status === 'Defaults restored'
        ? { message: status, tone: 'restored' }
        : status
          ? { message: status, tone: 'success' }
          : pendingChanges.length > 0
            ? { message: `Draft changes · ${pendingChanges.length} pending`, tone: 'draft' }
            : { message: 'Live', tone: 'live' };
  const storageNotReady = agentsStatus != null && !agentsStatus.supabase_configured;

  // Clicking a rail item scrolls its section to the top of the reading column.
  // The scroll-spy observer below then confirms the active state from what's
  // actually on screen, so a click and a manual scroll converge on one source.
  const scrollToSection = (id: SectionId) => {
    setActiveSection(id);
    const target = contentScrollRef.current?.querySelector<HTMLElement>(`#${id}`);
    target?.scrollIntoView({ behavior: reduceMotion ? 'auto' : 'smooth', block: 'start' });
  };

  useEffect(() => {
    if (!settings || !requestedSectionId || requestedSectionHandledRef.current === requestedSectionId) return;
    requestedSectionHandledRef.current = requestedSectionId;
    setActiveSection(requestedSectionId);
    const frame = window.requestAnimationFrame(() => {
      const target = contentScrollRef.current?.querySelector<HTMLElement>(`#${requestedSectionId}`);
      target?.scrollIntoView({ behavior: reduceMotion ? 'auto' : 'smooth', block: 'start' });
    });
    return () => window.cancelAnimationFrame(frame);
  }, [settings, requestedSectionId, reduceMotion]);

  // Scroll-spy: the section nearest the top of the reading column wins. Rebinds
  // once the settings payload resolves (sections mount) — never on every draft
  // edit, so typing in a field can't thrash the observer.
  useEffect(() => {
    const root = contentScrollRef.current;
    if (!root) return;
    const targets = SETTINGS_SECTIONS
      .map((section) => root.querySelector<HTMLElement>(`#${section.id}`))
      .filter((node): node is HTMLElement => node != null);
    if (!targets.length) return;

    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((entry) => entry.isIntersecting)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio);
        const id = visible[0]?.target.getAttribute('id') as SectionId | null;
        if (id) setActiveSection(id);
      },
      { root, rootMargin: '-15% 0px -70% 0px', threshold: [0, 0.25, 0.6] },
    );
    targets.forEach((target) => observer.observe(target));
    return () => observer.disconnect();
  }, [settings]);

  const updateDraft = (updater: (current: FundConfiguration) => FundConfiguration) => {
    setDraft((current) => updater(current));
    setPreRestoreDraft(null);
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
  const getDeploymentErrors = () => [
    ...(weightValidation.valid ? [] : [`Scoring weights total ${weightValidation.total}%, not 100%.`]),
    ...bandValidation.errors,
    ...thresholdValidation.errors,
  ];

  const routeDeploymentErrors = (messages: string[], source: AttentionSource) => {
    if (!messages.length) return;
    setErrors(messages);
    const section = sectionForDeploymentError(messages[0]);
    setAttention({ section, source });
    setActiveSection(section);
    document.getElementById(section)?.scrollIntoView({ behavior: reduceMotion ? 'auto' : 'smooth', block: 'start' });
    requestAnimationFrame(() => {
      requestAnimationFrame(() => document.getElementById(section)?.focus());
    });
  };

  const performDeploy = async () => {
    if (!settings) return;
    const retryCheckpoint = pendingPolicyPublish;
    const nextErrors = retryCheckpoint ? [] : getDeploymentErrors();
    if (nextErrors.length) {
      routeDeploymentErrors(nextErrors, 'local');
      return;
    }
    setSaving(true);
    setErrors([]);
    setStatus(null);
    const deployedDraftSnapshot = serializeDecisionConfig(draft);
    let checkpoint = retryCheckpoint;

    try {
      let persistedSettings: Settings | null = null;
      if (!checkpoint) {
        // Step 1 — persist settings; the backend republishes the fund thesis
        // when mandate content changed (no-op otherwise).
        const mapped = mapFundConfigToSettings(draft, settings);
        const result = await patchSettings(mapped);
        if (result.error) {
          routeDeploymentErrors(
            result.error.errors.length ? result.error.errors : [result.error.message],
            'server',
          );
          return;
        }
        persistedSettings = result.data ?? null;
        const fundConfig = persistedSettings?.fund_config ?? draft;
        const checkpointSettings = persistedSettings ?? settings;
        const storageKey = getPolicyPublishRecoveryStorageKey(userId, checkpointSettings);
        checkpoint = { fundConfig, storageKey };
        savePolicyPublishRecovery(
          getPolicyPublishRecoveryStorage(),
          storageKey,
          checkpointSettings,
          fundConfig,
        );
        setPendingPolicyPublish(checkpoint);
        setSavedSnapshot(serializeDecisionConfig(fundConfig));
        if (persistedSettings) setSettings(persistedSettings);
      }

      // Step 2 — publish the scoring policy. A checkpoint makes a failed
      // publish independently retryable without republishing the thesis.
      const policyResult = await publishPolicy(checkpoint.fundConfig);
      if (policyResult.error) {
        const policyError = policyResult.error.errors.length
          ? policyResult.error.errors.join(' ')
          : policyResult.error.message;
        routeDeploymentErrors(
          [`Settings and fund thesis are live, but the scoring policy did not publish: ${policyError}`],
          'server',
        );
        return;
      }
      setPendingPolicyPublish(null);
      clearPolicyPublishRecovery(getPolicyPublishRecoveryStorage(), checkpoint.storageKey);

      // Step 3 — reconcile local state with what is now live (policy publish
      // rewrites fund_config pointers server-side, so refetch is the authority).
      const refreshed = await fetchSettings().catch(() => null);
      const summary = await fetchFundThesisSummary().catch(() => null);
      const liveSettings = refreshed ?? persistedSettings ?? settings;
      setSettings(liveSettings);
      let liveConfig = liveSettings.fund_config ?? checkpoint.fundConfig;
      if (policyResult.policy?.policy_version_id && policyResult.policy.policy_hash) {
        liveConfig = {
          ...liveConfig,
          activePolicyVersionId: policyResult.policy.policy_version_id,
          publishedPolicyHash: policyResult.policy.policy_hash,
          draftPolicyHash: policyResult.policy.policy_hash,
          lastPublishedAt: policyResult.policy.published_at ?? new Date().toISOString(),
        };
      }
      if (summary?.active_version_number != null) {
        setThesisSummary(summary);
        liveConfig = applyThesisVersionMetadata(liveConfig, summary.active_version_number);
      }
      const saved = saveLocalConfiguration(liveConfig);
      setConfiguration(saved);
      const draftStillMatchesTransaction =
        serializeDecisionConfig(draftRef.current) === deployedDraftSnapshot
        && deployedDraftSnapshot === serializeDecisionConfig(checkpoint.fundConfig);
      setDraft((current) => draftStillMatchesTransaction
        ? saved
        : {
            ...current,
            activePolicyVersionId: saved.activePolicyVersionId,
            draftPolicyHash: saved.draftPolicyHash,
            publishedPolicyHash: saved.publishedPolicyHash,
            lastPublishedAt: saved.lastPublishedAt,
          });
      setSavedSnapshot(serializeDecisionConfig(saved));
      await Promise.allSettled([
        queryClient.invalidateQueries({ queryKey: ['settings'] }),
        queryClient.invalidateQueries({ queryKey: ['fund-thesis'] }),
      ]);

      const thesisPart = summary?.active_version_number != null
        ? ` · ${thesisVersionLabel(summary.active_version_number)}`
        : '';
      const policyPart = policyResult.policy ? ` · policy ${policyResult.policy.policy_version_id}` : '';
      setStatus(draftStillMatchesTransaction ? `Deployed — configuration is live${thesisPart}${policyPart}.` : null);
      setErrors([]);
      setAttention(null);
    } catch (error) {
      const message = error instanceof Error && error.message
        ? error.message
        : 'The deployment request failed. Try again.';
      const prefix = checkpoint
        ? 'Settings and fund thesis are live, but the scoring policy did not publish: '
        : 'Deployment failed: ';
      routeDeploymentErrors([`${prefix}${message}`], 'server');
    } finally {
      setSaving(false);
    }
  };

  const requestDeploy = () => {
    if (saving) return;
    if (pendingPolicyPublish) {
      void performDeploy();
      return;
    }
    const nextErrors = getDeploymentErrors();
    if (nextErrors.length) {
      routeDeploymentErrors(nextErrors, 'local');
      return;
    }
    const confirmation = getDeploymentConfirmation(
      draft,
      savedSnapshot,
      (thesisSummary?.active_version_number ?? 0) > 0,
    );
    if (confirmation) {
      setThesisConfirmation(confirmation);
      return;
    }
    void performDeploy();
  };

  const confirmThesisDeployment = () => {
    setThesisConfirmation(null);
    void performDeploy();
  };

  const restoreDefaults = () => {
    if (!settings) return;
    const next = createDefaultFundConfiguration({ ...settings, fund_config: undefined });
    setPreRestoreDraft(draft);
    setDraft(next);
    setDialog(null);
    setStatus('Defaults restored');
    setErrors([]);
  };

  const undoRestore = () => {
    if (!preRestoreDraft) return;
    setDraft(preRestoreDraft);
    setPreRestoreDraft(null);
    setStatus(null);
    setErrors([]);
  };

  const navigateBack = () => navigate('/v1');

  const requestExit = () => {
    if (hasPendingPolicyChanges) {
      setDialog('leave');
      return;
    }
    navigateBack();
  };

  const discardAndLeave = () => {
    setDraft(configuration);
    setPreRestoreDraft(null);
    setDialog(null);
    navigateBack();
  };

  useEffect(() => {
    if (!hasPendingPolicyChanges) return;
    const warnBeforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = '';
    };
    window.addEventListener('beforeunload', warnBeforeUnload);
    return () => window.removeEventListener('beforeunload', warnBeforeUnload);
  }, [hasPendingPolicyChanges]);

  // In-place loader keeps the application frame mounted while settings resolve.
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
          <div className="max-w-md px-phi-5 text-center">
            <p className={sectionLabelCls}>Settings unavailable</p>
            <p className="mt-phi-2 type-body-sm text-oxford/70">
              Aethria could not load your settings. Retry now, or return to the workspace.
            </p>
            <div className="mt-phi-4 flex flex-wrap items-center justify-center gap-phi-3">
              <button
                type="button"
                onClick={() => void settingsQuery.refetch()}
                disabled={settingsQuery.isFetching}
                aria-busy={settingsQuery.isFetching}
                className="btn-aethria-solid disabled:cursor-wait disabled:opacity-50"
              >
                Retry
              </button>
              <button
                type="button"
                onClick={navigateBack}
                className="type-action inline-flex min-h-11 items-center px-phi-3 text-oxford/70 transition-colors hover:text-oxford focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-oxford/30"
              >
                Back to Aethria
              </button>
            </div>
          </div>
        </main>
      </div>
    );
  }

  return (
    <div className="page-transition-enter settings-gallery-room flex min-h-0 flex-1 flex-col overflow-hidden lg:pl-[var(--spine-width)]">
      <SettingsTopBar
        live={pendingChanges.length === 0 && pendingPolicyPublish == null}
        saving={saving}
        message={topBarStatus.message}
        tone={topBarStatus.tone}
        canUndo={preRestoreDraft != null}
        onBack={requestExit}
        onRestoreDefaults={() => setDialog('restore')}
        onUndo={undoRestore}
        onDeploy={requestDeploy}
        actionLabel={pendingPolicyPublish ? (saving ? 'Retrying…' : 'Retry publish') : (saving ? 'Deploying…' : 'Deploy changes')}
        activeSection={activeSection}
        attentionSection={attentionSection}
        onNavigate={scrollToSection}
      />

      <div className="flex min-h-0 flex-1 overflow-hidden">
        <div
          ref={contentScrollRef}
          className="min-h-0 flex-1 overflow-y-auto overscroll-contain bg-paper"
        >
          <SettingsMobileNav
            activeSection={activeSection}
            attentionSection={attentionSection}
            onSelect={scrollToSection}
          />
          <div className="sticky top-[3.75rem] z-10 lg:top-0">
            <OperationsStrip
              variant="bar"
              settings={settings}
              storageUnavailable={storageNotReady}
              onSettingsChange={setSettings}
            />
          </div>
          {/* The room's own arrival is the page transition on the root; a second
              entrance here just re-faded content that had already arrived. */}
          <main
            className={`${workspaceLayout.pageBottom} settings-gallery-content mx-auto w-full overflow-y-visible`}
          >
            <div className="settings-gallery-plate">
              <header className="settings-gallery-plate-head">
                <h1>Settings</h1>
              </header>
              <p className="settings-gallery-intro">Define what you invest in, how deals are scored, and how the pipeline operates.</p>
                  <SettingsGroup
                    title="Fund thesis"
                    description="Your investment mandate. Publishing creates the thesis version used by Scout, Reviewer, and Partner."
                  >

                  <RoomSection
                    id="thesis"
                    title="Fund thesis"
                    label="Fund thesis"
                  >
                    <SpecRow label="Identity">
                      <div className="grid gap-phi-5 md:grid-cols-2">
                        <TextField id="fund-name" label="Fund name" value={draft.mandate.fundName} onChange={(value) => updateMandate('fundName', String(value))} />
                        <TextField id="mandate-name" label="Mandate name" value={draft.mandate.mandateName} onChange={(value) => updateMandate('mandateName', String(value))} />
                      </div>
                    </SpecRow>
                    <SpecRow label="Where to invest">
                      <div className="grid gap-phi-5">
                        <ChipGroup label="Preferred stages" options={stageOptions} selected={draft.mandate.preferredStages} onChange={(value) => updateMandate('preferredStages', value)} />
                        <div className="flex flex-col gap-phi-2">
                          <ChipGroup label="Geographies" options={geographyOptions} selected={draft.mandate.geographies} onChange={(value) => updateMandate('geographies', value)} />
                          <p className={metaCls}>UK/Ireland is listed separately from Europe. Global includes all regions.</p>
                        </div>
                        <TextField id="custom-geography" label="Custom geography" value={draft.mandate.customGeography} onChange={(value) => updateMandate('customGeography', String(value))} />
                      </div>
                    </SpecRow>
                    <SpecRow label="What to invest in">
                      <div className="grid gap-phi-5">
                        <ChipGroup label="Sectors" options={sectorOptions} selected={draft.mandate.sectors} onChange={(value) => updateMandate('sectors', value)} />
                        <div className="grid gap-phi-5 md:grid-cols-2">
                          <TextField id="custom-sectors" label="Custom sectors" value={draft.mandate.customSectors} onChange={(value) => updateMandate('customSectors', String(value))} />
                          <TextField id="excluded-sectors" label="Excluded sectors" value={draft.mandate.excludedSectors} onChange={(value) => updateMandate('excludedSectors', String(value))} />
                        </div>
                        <TextField id="business-models" label="Preferred business models" value={draft.mandate.businessModels} onChange={(value) => updateMandate('businessModels', String(value))} />
                      </div>
                    </SpecRow>
                    <SpecRow label="Economics">
                      <div className="grid gap-phi-5 md:grid-cols-3">
                        <TextField id="check-min" label="Minimum check size (USD)" type="number" value={draft.mandate.checkSizeMin} onChange={(value) => updateMandate('checkSizeMin', Number(value))} min={0} />
                        <TextField id="check-max" label="Maximum check size (USD)" type="number" value={draft.mandate.checkSizeMax} onChange={(value) => updateMandate('checkSizeMax', Number(value))} min={0} />
                        <TextField id="ownership" label="Ownership target %" type="number" value={draft.mandate.ownershipTarget} onChange={(value) => updateMandate('ownershipTarget', Number(value))} min={0} max={100} />
                      </div>
                    </SpecRow>
                    <SpecRow label="Proof required">
                      <TextField id="minimum-traction" label="Minimum traction expectations" value={draft.mandate.minimumTraction} onChange={(value) => updateMandate('minimumTraction', String(value))} />
                    </SpecRow>
                    <SpecRow label="Thesis narrative">
                      <TextAreaField id="thesis-text" label="Notes / thesis text" rows={7} value={draft.mandate.thesisText} onChange={(value) => updateMandate('thesisText', value)} />
                    </SpecRow>
                  </RoomSection>

                  <RoomSection
                    id="version"
                    title="Version"
                    label="Live state"
                  >
                    <SpecRow label="Draft">
                      <p className="type-body-sm text-oxford">{draft.versionLabel}</p>
                    </SpecRow>
                    <SpecRow label="Live thesis">
                      <p className="type-body-sm text-oxford">
                        {thesisSummary?.active_version_number != null
                          ? `Fund Thesis v${thesisSummary.active_version_number}`
                          : 'Not published'}
                      </p>
                    </SpecRow>
                    <SpecRow label="Storage">
                      <p className="type-body-sm text-oxford/65">
                        {storageNotReady ? 'Unavailable' : 'Ready'}
                      </p>
                    </SpecRow>
                  </RoomSection>

                  </SettingsGroup>

                  <SettingsGroup
                    title="Decision policy"
                    description="How evidence is scored, escalated, and routed. Changes stay in draft until you deploy a new policy version."
                  >

                {!bandValidation.valid && (
                  <div className="border-l-2 border-escalation/35 bg-escalation/[0.035] py-phi-3 pl-phi-3">
                    {bandValidation.errors.map((error) => <p key={error} className="type-body-sm text-escalation/75">{error}</p>)}
                  </div>
                )}

                  <RoomSection
                    id="thresholds"
                    title="Decision thresholds"
                    label="Thresholds"
                    description="Set the score boundaries for Pass, Monitor, and Invest, plus the conditions that control review freshness and scout confidence."
                  >
                    <DecisionThresholdsPanel
                      draft={draft}
                      updateDraft={updateDraft}
                      updateThreshold={updateThreshold}
                    />
                  </RoomSection>

                  <RoomSection
                    id="sensitivity"
                    title="Escalation sensitivity"
                    label="Risk posture"
                  >
                    <div className="flex flex-col gap-phi-3 py-phi-5">
                      <label htmlFor="risk-sensitivity" className={labelCls}>Sensitivity</label>
                      <select id="risk-sensitivity" value={draft.risk.sensitivity} onChange={(event) => updateRisk('sensitivity', event.target.value as RiskSensitivity)} className={selectCls} style={selectStyle}>
                        <option value="conservative">Conservative · surface more risk</option>
                        <option value="balanced">Balanced · standard review</option>
                        <option value="aggressive">Aggressive · surface only stronger risk</option>
                      </select>
                    </div>
                  </RoomSection>

                <RoomSection
                  id="weights"
                  title="Scoring weights"
                  label="Reviewer mix"
                >
                  <div className="flex flex-col">
                    <div className="flex flex-wrap items-baseline justify-between gap-phi-4 py-phi-5">
                      <div className="flex items-baseline gap-phi-3">
                        <p className={`type-data text-[1.6rem] ${weightValidation.valid ? 'text-oxford' : 'text-escalation/75'}`}>{weightValidation.total}%</p>
                        <p className="type-label-section text-xs text-oxford/70">Total weight</p>
                      </div>
                      <p className="type-note text-oxford/70">Adjust one — the rest rebalance to 100</p>
                    </div>
                    <div className="grid grid-cols-2 gap-phi-3 py-phi-3 sm:grid-cols-5">
                    {draft.scoringWeights.map((item) => (
                      <div key={item.key} className="flex min-w-0 flex-col items-center gap-phi-2 px-phi-2 py-phi-4 text-center">
                        <p className="type-label-section text-[10px] leading-tight text-oxford/60">{item.label}</p>
                        <input
                          type="number"
                          min={0}
                          max={100}
                          value={item.weight}
                          onChange={(event) => updateDraft((current) => ({
                            ...current,
                            scoringWeights: rebalanceWeights(current.scoringWeights, item.key, Number(event.target.value)),
                          }))}
                          className="type-display w-full border-0 bg-transparent p-0 text-center text-[clamp(1.8rem,3vw,2.6rem)] leading-none text-oxford outline-none focus:ring-0"
                          aria-label={`${item.label} weight`}
                        />
                      </div>
                    ))}
                    </div>
                    <p className="pt-phi-4 type-note text-oxford/70">
                      {draft.activePolicyVersionId
                        ? `Live policy ${draft.activePolicyVersionId}. Deploying publishes the next version.`
                        : 'Deploy to publish the first scoring policy.'}
                    </p>
                  </div>
                </RoomSection>

                  <RoomSection
                    id="memo"
                    title="Memo output"
                    label="Presentation"
                  >
                    <div className="grid gap-phi-7 py-phi-5 md:grid-cols-2">
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
                    <div className="grid gap-x-phi-7 md:grid-cols-2">
                      <ToggleRow id="deep-dive-collapsed" checked={draft.memo.deepDiveCollapsed} onChange={(value) => updateMemo('deepDiveCollapsed', value)} label="Collapse deep dive by default" />
                      <ToggleRow id="evidence-excerpts" checked={draft.memo.includeEvidenceExcerpts} onChange={(value) => updateMemo('includeEvidenceExcerpts', value)} label="Include evidence excerpts" />
                      <ToggleRow id="missing-data" checked={draft.memo.includeMissingData} onChange={(value) => updateMemo('includeMissingData', value)} label="Include missing-data section" />
                      <ToggleRow id="score-reasoning" checked={draft.memo.includeScoreReasoning} onChange={(value) => updateMemo('includeScoreReasoning', value)} label="Include score reasoning" />
                      <ToggleRow id="source-confidence" checked={draft.memo.includeSourceConfidence} onChange={(value) => updateMemo('includeSourceConfidence', value)} label="Include source confidence" />
                    </div>
                  </RoomSection>

                  <RoomSection
                    id="workflow"
                    title="Decision review workflow"
                    label="Governance"
                  >
                    <div className="py-phi-3">
                      <ToggleRow id="risk-ack" checked={draft.risk.requireAcknowledgement} onChange={(value) => updateRisk('requireAcknowledgement', value)} label="Require acknowledgement before ruling" hint="High-risk pending deals need a reviewed-risk step before Commit." />
                      <ToggleRow id="risk-high-only" checked={draft.risk.onlyGateHighSeverity} onChange={(value) => updateRisk('onlyGateHighSeverity', value)} label="Only gate high severity risks" hint="Medium adverse items stay visible without blocking the ruling." />
                    </div>
                  </RoomSection>

                  </SettingsGroup>

                  <SettingsGroup
                    title="Workspace runtime"
                    description="Operational limits for this workspace. Changes here save immediately and affect the running system."
                  >

                  <RoomSection
                    id="budget"
                    title="Cost budget"
                    label="Live limits"
                  >
                    <div className="grid gap-x-phi-8 sm:grid-cols-2">
                      <SpecRow label="Token limit per run"><p className="type-data text-[1.35rem]">{settings.cost_budget.max_tokens_per_run.toLocaleString()} tokens</p></SpecRow>
                      <SpecRow label="Cooldown between runs"><p className="type-data text-[1.35rem]">{settings.cost_budget.cooldown_seconds}s</p></SpecRow>
                      <SpecRow label="Daily spend ceiling (USD)"><p className="type-data text-[1.35rem]">${settings.cost_budget.daily_cost_ceiling.toLocaleString()}</p></SpecRow>
                      <SpecRow label="Weekly spend ceiling (USD)"><p className="type-data text-[1.35rem]">${settings.cost_budget.weekly_cost_ceiling.toLocaleString()}</p></SpecRow>
                    </div>
                    <p className="pt-phi-5 type-note text-oxford/70">Enforcement is {settings.cost_budget.enabled ? 'on' : 'off'} — toggle it in the rail.</p>
                  </RoomSection>

                  </SettingsGroup>

                  <SettingsGroup
                    title="System"
                    description="Agent governance, readiness, and operator diagnostics. Changes to prompts and calibration remain explicitly reviewed."
                  >

                  <RoomSection
                    id="governance"
                    title="Agent governance"
                    label="Advanced controls"
                  >
                    <p className="type-body-sm max-w-2xl pb-phi-4 leading-relaxed text-oxford/65">
                      Review correction proposals, test prompt drafts, and publish governed changes.
                      The Fund page keeps the readable learning record; operational controls live here.
                    </p>
                    {governanceEnabled ? (
                      <MetaCommandTab
                        reports={metaReportsQuery.data ?? []}
                        weights={scoutWeightsQuery.data ?? {
                          MarketDrivenScout: 0.25,
                          BuilderTechnicalScout: 0.25,
                          PainPointScout: 0.25,
                          ContrarianScout: 0.25,
                        }}
                        calibration={calibrationQuery.data ?? {
                          confidence_threshold_override: null,
                          reviewer_weak_threshold_override: null,
                          reviewer_strong_threshold_override: null,
                          last_calibrated_at: null,
                          last_calibrated_cycle: 0,
                          calibration_history: [],
                        }}
                        promptState={metaPromptStateQuery.data ?? { active: {}, active_detail: {}, pending: [] }}
                        metaEvalSet={metaEvalSetQuery.data ?? { startup_ids: [], count: 0, max: 50 }}
                        insights={metaInsightsQuery.data ?? null}
                        fundConfiguration={draft}
                      />
                    ) : (
                      <p className="type-note py-phi-4 text-oxford/60">
                        Select Agent governance in the Settings rail to load advanced controls.
                      </p>
                    )}
                  </RoomSection>

                  <RoomSection
                    id="system"
                    title="System state"
                    label="Run gates"
                    description="Shows whether the services and policies required to run the pipeline are ready."
                  >
                    {agentsStatus ? (
                      <div className="border-t border-oxford/[0.06]">
                        <EditorialStatus
                          label="Storage access"
                          value={agentsStatus.supabase_configured ? 'Ready' : 'Unavailable'}
                          detail={agentsStatus.supabase_configured ? undefined : 'Supabase required to run the pipeline.'}
                          tone={agentsStatus.supabase_configured ? 'ready' : 'warning'}
                        />
                        <EditorialStatus
                          label="AI provider access"
                          value={agentsStatus.openai_configured ? 'Ready' : 'Unavailable'}
                          detail={agentsStatus.openai_configured ? undefined : 'API key required to run the pipeline.'}
                          tone={agentsStatus.openai_configured ? 'ready' : 'warning'}
                        />
                        <EditorialStatus
                          label="Pipeline worker"
                          value={agentsStatus.worker_ready ? 'Ready' : 'Not ready'}
                          tone={agentsStatus.worker_ready ? 'ready' : 'warning'}
                        />
                        <EditorialStatus
                          label="Execution prerequisites"
                          value={agentsStatus.execution_prerequisites_ready ? 'Ready' : 'Blocked'}
                          detail={agentsStatus.execution_prerequisites_ready ? undefined : (agentsStatus.execution_prerequisite_detail ?? 'An active thesis and published policy are required.')}
                          tone={agentsStatus.execution_prerequisites_ready ? 'ready' : 'warning'}
                        />
                        <EditorialStatus
                          label="Pipeline availability"
                          value={agentsStatus.agents_will_run ? 'Able to run' : 'Blocked'}
                          detail={agentsStatus.agents_will_run ? undefined : (agentsStatus.execution_prerequisite_detail ?? agentsStatus.thesis_error ?? (agentsStatus.durable_job_error ? 'The durable job store is unreachable.' : null) ?? 'A required gate is not ready.')}
                          tone={agentsStatus.agents_will_run ? 'ready' : 'warning'}
                        />
                      </div>
                    ) : (
                      <div className="py-phi-5">
                        <p className="type-body-sm text-oxford">Status unavailable</p>
                        <p className="mt-phi-2 type-note leading-relaxed text-oxford/70">
                          Aethria could not read the agent status endpoint. Runtime switch values above still reflect saved settings.
                        </p>
                      </div>
                    )}
                    <ExecutionReadinessPanel
                      status={systemStatusQuery.data ?? null}
                      recentJobs={recentJobsQuery.data ?? []}
                      loading={systemStatusQuery.isPending}
                      compact
                    />
                  </RoomSection>
                  </SettingsGroup>
            </div>
          </main>
        </div>
      </div>

      <FundThesisConfirmationModal
        open={thesisConfirmation != null}
        changes={thesisConfirmation?.changes ?? []}
        firstPublication={thesisConfirmation?.firstPublication ?? false}
        busy={saving}
        onCancel={() => setThesisConfirmation(null)}
        onConfirm={confirmThesisDeployment}
      />
      <SettingsActionDialog
        open={dialog === 'restore'}
        title="Restore default settings?"
        description="This replaces your current draft with the default fund policy. Your live policy remains unchanged until you deploy."
        confirmLabel="Restore defaults"
        busy={saving}
        onCancel={() => setDialog(null)}
        onConfirm={restoreDefaults}
      />
      <SettingsActionDialog
        open={dialog === 'leave'}
        title="Leave settings?"
        description="Your policy draft has undeployed changes. Keep editing, or discard the draft and return to the live configuration."
        confirmLabel="Discard and leave"
        busy={saving}
        destructive
        onCancel={() => setDialog(null)}
        onConfirm={discardAndLeave}
      />
    </div>
  );
}
