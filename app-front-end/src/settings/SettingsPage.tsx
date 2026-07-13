import { useEffect, useMemo, useRef, useState, type CSSProperties, type KeyboardEvent } from 'react';
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
import { useFundConfiguration } from '../hooks';
import DecisionThresholdsPanel from './DecisionThresholdsPanel';
import FundThesisConfirmationModal from './FundThesisConfirmationModal';
import OperationsStrip from './OperationsStrip';
import { validateDecisionThresholds } from '../lib/decisionThresholds';
import {
  SETTINGS_SECTIONS,
  getDeploymentConfirmation,
  getPendingChanges,
  serializeDecisionConfig,
  tabForSection,
  type PendingChange,
  type FundThesisChangeSet,
  type SectionId,
  type SettingsTab,
} from './settingsModel';
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
const labelCls = 'type-label-section';
const sectionLabelCls = 'type-label-section';
const metaCls = 'type-meta';
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
    <div className="flex items-center justify-between gap-phi-5 py-phi-3">
      <div className="min-w-0">
        <label htmlFor={id} className="type-body-sm text-oxford">{label}</label>
        {hint && <p className="type-note mt-phi-1 leading-snug text-oxford/60">{hint}</p>}
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
              className={`type-action inline-flex min-h-[36px] items-center justify-center rounded-none px-phi-3 transition-colors ${active ? 'bg-oxford text-paper' : 'bg-oxford/[0.045] hover:bg-oxford/[0.075]'}`}
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
    <section id={id} className={`scroll-mt-phi-6 py-phi-8 first:pt-0 ${className ?? ''}`}>
      <div className="grid gap-phi-6 lg:grid-cols-[minmax(10rem,22%)_minmax(0,1fr)] lg:gap-phi-8">
        <div>
          <p className={sectionLabelCls}>{title}</p>
          <p className="mt-phi-3 max-w-[17rem] type-body-sm leading-relaxed text-oxford/60">{kicker}</p>
        </div>
        <div className="min-w-0">{children}</div>
      </div>
    </section>
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
  detail: string;
  tone?: 'neutral' | 'ready' | 'warning';
}) {
  const dotClass = tone === 'ready'
    ? 'bg-oxford'
    : tone === 'warning'
      ? 'bg-escalation/75'
      : 'bg-oxford/30';
  return (
    <div className="grid gap-phi-1 py-phi-3 md:grid-cols-[minmax(8rem,20%)_minmax(9rem,24%)_minmax(0,1fr)] md:items-baseline md:gap-phi-5">
      <p className="type-label-section text-oxford/65">{label}</p>
      <p className="type-body-sm inline-flex items-center gap-phi-2 text-oxford">
        <span className={`h-1.5 w-1.5 shrink-0 ${dotClass}`} aria-hidden />
        {value}
      </p>
      <p className="type-note leading-relaxed text-oxford/60">{detail}</p>
    </div>
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
  const [thesisConfirmation, setThesisConfirmation] = useState<FundThesisChangeSet | null>(null);
  const [activeTab, setActiveTab] = useState<SettingsTab>('decision');
  const [activeSection, setActiveSection] = useState<SectionId>('thesis');
  const [agentsStatus, setAgentsStatus] = useState<AgentsStatus | null>(null);
  const [thesisSummary, setThesisSummary] = useState<FundThesisSummary | null>(null);
  const [savedSnapshot, setSavedSnapshot] = useState('');
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
    setSavedSnapshot(serializeDecisionConfig(configuration));
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

    const targets = SETTINGS_SECTIONS
      .filter((section) => section.tab === activeTab)
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
  }, [activeTab, loading, settings]);

  const weightValidation = useMemo(() => validateWeights(draft.scoringWeights), [draft.scoringWeights]);
  const bandValidation = useMemo(() => validateScoreBands(draft.scoreBands), [draft.scoreBands]);
  const thresholdValidation = useMemo(() => validateDecisionThresholds(draft), [draft]);

  // Draft vs Live only covers deployable decision configuration. Runtime
  // controls save independently in OperationsStrip and never enter this list.
  const pendingChanges = useMemo<PendingChange[]>(
    () => getPendingChanges(draft, savedSnapshot),
    [draft, savedSnapshot],
  );
  const unsaved = pendingChanges.length > 0;
  const storageNotReady = agentsStatus != null && !agentsStatus.supabase_configured;

  const selectTab = (tab: SettingsTab) => {
    setActiveTab(tab);
    const firstSection = SETTINGS_SECTIONS.find((section) => section.tab === tab);
    if (firstSection) setActiveSection(firstSection.id);
    contentScrollRef.current?.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const handleTabKeyDown = (event: KeyboardEvent<HTMLButtonElement>) => {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
    event.preventDefault();
    const nextTab: SettingsTab = event.key === 'ArrowLeft' || event.key === 'Home'
      ? 'decision'
      : 'admin';
    selectTab(nextTab);
    requestAnimationFrame(() => document.getElementById(`settings-tab-${nextTab}`)?.focus());
  };

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
  const getDeploymentErrors = () => [
    ...(weightValidation.valid ? [] : [`Scoring weights total ${weightValidation.total}%, not 100%.`]),
    ...bandValidation.errors,
    ...thresholdValidation.errors,
  ];

  const performDeploy = async () => {
    if (!settings) return;
    const nextErrors = getDeploymentErrors();
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
    let liveConfig = liveSettings.fund_config ?? draft;
    if (summary?.active_version_number != null) {
      setThesisSummary(summary);
      liveConfig = applyThesisVersionMetadata(liveConfig, summary.active_version_number);
    }
    const saved = saveLocalConfiguration(liveConfig);
    setConfiguration(saved);
    setDraft(saved);
    setSavedSnapshot(serializeDecisionConfig(saved));
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

  const requestDeploy = () => {
    if (saving) return;
    const nextErrors = getDeploymentErrors();
    if (nextErrors.length) {
      setErrors(nextErrors);
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

  const handleReset = () => {
    const next = clearFundConfiguration(settings);
    setConfiguration(next);
    setDraft(next);
    setSavedSnapshot(serializeDecisionConfig(next));
    setStatus(null);
    setErrors([]);
  };

  // ── The spine is the only rail: project section nav + draft state into it. ──
  // Handlers (and the pending list) are reached through refs so the projection
  // effect re-runs only when displayed values change, never on identity.
  const lastDeployedAt = draft.lastPublishedAt ?? draft.lastSavedAt;
  const spineActionsRef = useRef({ deploy: () => {}, reset: () => {} });
  spineActionsRef.current = { deploy: requestDeploy, reset: handleReset };
  const pendingRef = useRef<PendingChange[]>(pendingChanges);
  pendingRef.current = pendingChanges;
  const pendingKey = pendingChanges.map((item) => item.label).join('|');

  useEffect(() => {
    const scrollToSection = (id: SectionId) => {
      const nextTab = tabForSection(id);
      setActiveTab(nextTab);
      setActiveSection(id);
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          const target = contentScrollRef.current?.querySelector<HTMLElement>(`#${id}`);
          target?.scrollIntoView({ behavior: 'smooth', block: 'start' });
        });
      });
    };
    const pending = pendingRef.current;
    setSpineOverride({
      nav: (
        <>
          <SpineNavButton
            label="← Home"
            active={false}
            ariaPressed={false}
            compact
            surface="oxford"
            onClick={() => navigate('/v1')}
          />
          {(['decision', 'admin'] as const).map((tab) => (
            <div key={tab}>
              <p className="type-label-section type-label-inverse px-2 pb-phi-1 pt-phi-4">
                {tab === 'decision' ? 'Decision' : 'Administration'}
              </p>
              {SETTINGS_SECTIONS.filter((section) => section.tab === tab).map((section) => (
                <SpineNavButton
                  key={section.id}
                  label={section.label}
                  active={activeTab === tab && activeSection === section.id}
                  ariaPressed={activeTab === tab && activeSection === section.id}
                  compact
                  surface="oxford"
                  onClick={() => scrollToSection(section.id)}
                />
              ))}
            </div>
          ))}
        </>
      ),
      footer: (
        <section aria-label="Deployment status" className="border-t border-white/[0.07] px-2 pt-phi-3">
          <div className="flex items-center justify-between gap-phi-2">
            <span className="type-status type-status-inverse">{unsaved ? 'Draft' : 'Live'}</span>
            <span
              className={`type-status inline-flex shrink-0 items-center gap-phi-2 ${
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
              className="type-action type-action-inverse inline-flex min-h-[32px] w-full items-center justify-center transition-colors hover:text-white/80 disabled:opacity-50 btn-interaction"
              title="Restore local defaults; deploy to make them live"
            >
              Reset to defaults
            </button>
          </div>
        </section>
      ),
    });
  }, [setSpineOverride, navigate, activeTab, activeSection, unsaved, saving, lastDeployedAt, pendingKey]);

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
              <p className={sectionLabelCls}>{activeTab === 'decision' ? 'Decision settings' : 'Administration'}</p>
              {unsaved ? (
                <p className="type-meta text-oxford/60">{pendingChanges.length} pending — not yet live</p>
              ) : null}
            </div>
            <button
              type="button"
              onClick={requestDeploy}
              disabled={saving || !unsaved}
              className="btn-aethria-solid disabled:cursor-not-allowed disabled:opacity-40"
            >
              {saving ? 'Deploying…' : 'Deploy changes'}
            </button>
              </div>

              <OperationsStrip
                settings={settings}
                storageUnavailable={storageNotReady}
                onSettingsChange={setSettings}
              />

              <div
                className="flex min-h-12 items-end gap-phi-5 border-b border-oxford/[0.09] px-phi-4 lg:px-phi-6"
                role="tablist"
                aria-label="Settings mode"
              >
                {(['decision', 'admin'] as const).map((tab) => {
                  const selected = activeTab === tab;
                  const label = tab === 'decision' ? 'Decision' : 'Administration';
                  return (
                    <button
                      key={tab}
                      id={`settings-tab-${tab}`}
                      type="button"
                      role="tab"
                      aria-selected={selected}
                      aria-controls={`settings-panel-${tab}`}
                      tabIndex={selected ? 0 : -1}
                      onClick={() => selectTab(tab)}
                      onKeyDown={handleTabKeyDown}
                      className={`relative min-h-11 px-phi-1 type-action transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-oxford/30 ${
                        selected ? 'text-oxford' : 'text-oxford/50 hover:text-oxford/75'
                      }`}
                    >
                      {label}
                      <span
                        className={`absolute inset-x-0 bottom-0 h-px transition-opacity ${selected ? 'bg-oxford opacity-100' : 'opacity-0'}`}
                        aria-hidden
                      />
                    </button>
                  );
                })}
              </div>

              <div ref={contentScrollRef} className="min-h-0 flex-1 overflow-y-auto scroll-smooth">
            <div
              id={`settings-panel-${activeTab}`}
              role="tabpanel"
              aria-labelledby={`settings-tab-${activeTab}`}
              className="min-h-full"
            >
              <div className="mx-auto flex w-full max-w-[68rem] min-w-0 flex-col px-phi-5 py-phi-7 lg:px-phi-7 lg:py-phi-8">
                <header className="mb-phi-7 max-w-[54rem]">
                  <p className="type-label-section">
                    {activeTab === 'decision' ? `Decision configuration · ${draft.versionLabel}` : 'Administration · output and operations'}
                  </p>
                  <h1 className="type-display mt-phi-3 text-[clamp(28px,3vw,42px)] leading-[1.08] text-oxford">
                    {activeTab === 'decision' ? 'How the fund decides' : 'How the system operates'}<span className="wordmark-dot">.</span>
                  </h1>
                  <p className="mt-phi-3 max-w-[42rem] type-body-sm leading-relaxed text-oxford/60">
                    {activeTab === 'decision'
                      ? 'Decision edits stay in draft until you deploy them. One deployment updates the fund thesis and scoring policy together.'
                      : 'Preferences below remain draft until deployed. Pipeline controls above save immediately.'}
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

                {activeTab === 'decision' ? (
                  <>
                <SettingsSection id="thesis" title="Fund thesis" kicker="Define the companies this fund is built to find, assess, and back.">
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
                    <div className="pt-phi-2">
                      <p className="type-note text-oxford/55">
                        {storageNotReady
                          ? 'Supabase storage is required to version the fund thesis.'
                          : thesisSummary
                            ? `Live: Fund Thesis v${thesisSummary.active_version_number}. Deploying a mandate change publishes the next version automatically.`
                            : 'No active thesis yet — deploying the mandate publishes v1.'}
                      </p>
                    </div>
                  </div>
                </SettingsSection>

                {!bandValidation.valid && (
                  <div className="mb-phi-5 border border-escalation/25 bg-escalation/[0.035] px-phi-4 py-phi-3">
                    {bandValidation.errors.map((error) => <p key={error} className="type-body-sm text-escalation/75">{error}</p>)}
                  </div>
                )}

                <SettingsSection id="thresholds" title="Decision thresholds" kicker="Set the score bands that turn analysis into PASS, MONITOR, or INVEST." className="border-t border-oxford/[0.06]">
                  <DecisionThresholdsPanel draft={draft} updateDraft={updateDraft} updateThreshold={updateThreshold} />
                </SettingsSection>

                <SettingsSection id="weights" title="Scoring weights" kicker="Set how much each reviewer dimension contributes to the overall score." className="border-t border-oxford/[0.06]">
                  <div className="flex flex-col gap-phi-4">
                    <div className="flex flex-wrap items-baseline justify-between gap-phi-4 pb-phi-2">
                      <div className="flex items-baseline gap-phi-3">
                        <p className={`type-data text-[1.6rem] ${weightValidation.valid ? 'text-oxford' : 'text-escalation/75'}`}>{weightValidation.total}%</p>
                        <p className="type-label-section">Total weight</p>
                      </div>
                      <p className="type-note text-oxford/60">Adjust one — the rest rebalance to 100</p>
                    </div>
                    {draft.scoringWeights.map((item) => (
                      <div key={item.key} className="grid gap-phi-3 py-phi-3 md:grid-cols-[minmax(150px,22%)_minmax(0,1fr)_92px] md:items-start">
                        <div>
                          <p className="type-body-emphasis text-oxford">{item.label}</p>
                          <p className="type-note mt-phi-1 leading-snug text-oxford/60">{item.description}</p>
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
                          className={`${inputCls} type-data text-right`}
                          aria-label={`${item.label} weight`}
                        />
                      </div>
                    ))}
                    <div className="pt-phi-3">
                      <p className="type-note leading-relaxed text-oxford/55">
                        {draft.activePolicyVersionId
                          ? `Live policy ${draft.activePolicyVersionId}${draft.lastPublishedAt ? ` · published ${formatDateTime(draft.lastPublishedAt)}` : ''}. Deploying scoring changes publishes the next version.`
                          : 'No scoring policy has been published yet. Deploy these settings to publish the first version.'}
                      </p>
                    </div>
                  </div>
                </SettingsSection>

                <SettingsSection id="sensitivity" title="Escalation sensitivity" kicker="Choose how readily adverse evidence is raised before a ruling." className="border-t border-oxford/[0.06]">
                  <div className="flex max-w-lg flex-col gap-phi-2">
                    <label htmlFor="risk-sensitivity" className={labelCls}>Sensitivity</label>
                    <select id="risk-sensitivity" value={draft.risk.sensitivity} onChange={(event) => updateRisk('sensitivity', event.target.value as RiskSensitivity)} className={selectCls} style={selectStyle}>
                      <option value="conservative">Conservative · surface more risk</option>
                      <option value="balanced">Balanced · standard review</option>
                      <option value="aggressive">Aggressive · surface only stronger risk</option>
                    </select>
                    <p className="type-note leading-relaxed text-oxford/60">This changes which signals are escalated, not whether a person must acknowledge them.</p>
                  </div>
                </SettingsSection>
                  </>
                ) : (
                  <>
                    <SettingsSection
                      id="memo"
                      title="Memo output"
                      kicker="Choose the shape, audience, and evidence shown in new investment memos."
                    >
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
                        <div className="grid gap-x-phi-7 md:grid-cols-2">
                          <ToggleRow id="deep-dive-collapsed" checked={draft.memo.deepDiveCollapsed} onChange={(value) => updateMemo('deepDiveCollapsed', value)} label="Collapse deep dive by default" />
                          <ToggleRow id="evidence-excerpts" checked={draft.memo.includeEvidenceExcerpts} onChange={(value) => updateMemo('includeEvidenceExcerpts', value)} label="Include evidence excerpts" />
                          <ToggleRow id="missing-data" checked={draft.memo.includeMissingData} onChange={(value) => updateMemo('includeMissingData', value)} label="Include missing-data section" />
                          <ToggleRow id="score-reasoning" checked={draft.memo.includeScoreReasoning} onChange={(value) => updateMemo('includeScoreReasoning', value)} label="Include score reasoning" />
                          <ToggleRow id="source-confidence" checked={draft.memo.includeSourceConfidence} onChange={(value) => updateMemo('includeSourceConfidence', value)} label="Include source confidence" />
                        </div>
                      </div>
                    </SettingsSection>

                    <SettingsSection
                      id="workflow"
                      title="Ruling workflow"
                      kicker="Control what must happen before a recommendation becomes a recorded ruling."
                      className="border-t border-oxford/[0.06]"
                    >
                      <div className="grid gap-x-phi-7 md:grid-cols-2">
                        <ToggleRow id="risk-ack" checked={draft.risk.requireAcknowledgement} onChange={(value) => updateRisk('requireAcknowledgement', value)} label="Require acknowledgement before ruling" hint="High-risk pending deals need a reviewed-risk step before Commit." />
                        <ToggleRow id="risk-high-only" checked={draft.risk.onlyGateHighSeverity} onChange={(value) => updateRisk('onlyGateHighSeverity', value)} label="Only gate high severity risks" hint="Medium adverse items stay visible without blocking the ruling." />
                      </div>
                    </SettingsSection>

                    <SettingsSection
                      id="budget"
                      title="Cost budget"
                      kicker="The live limits that constrain model usage. Enable or pause enforcement from the strip above."
                      className="border-t border-oxford/[0.06]"
                    >
                      <div className="grid gap-x-phi-8 gap-y-phi-5 sm:grid-cols-2">
                        <div><p className={labelCls}>Per run</p><p className="type-data mt-phi-2 text-[1.35rem]">{settings.cost_budget.max_tokens_per_run.toLocaleString()} tokens</p></div>
                        <div><p className={labelCls}>Cooldown</p><p className="type-data mt-phi-2 text-[1.35rem]">{settings.cost_budget.cooldown_seconds}s</p></div>
                        <div><p className={labelCls}>Daily ceiling</p><p className="type-data mt-phi-2 text-[1.35rem]">${settings.cost_budget.daily_cost_ceiling.toLocaleString()}</p></div>
                        <div><p className={labelCls}>Weekly ceiling</p><p className="type-data mt-phi-2 text-[1.35rem]">${settings.cost_budget.weekly_cost_ceiling.toLocaleString()}</p></div>
                      </div>
                      <p className="mt-phi-5 type-note text-oxford/55">Budget enforcement is {settings.cost_budget.enabled ? 'on' : 'off'} and saves immediately when changed above.</p>
                    </SettingsSection>

                    <SettingsSection
                      id="system"
                      title="System state"
                      kicker="A compact view of the gates that determine whether the pipeline can run."
                      className="border-t border-oxford/[0.06]"
                    >
                      {agentsStatus ? (
                        <div>
                          <EditorialStatus
                            label="Storage"
                            value={agentsStatus.supabase_configured ? 'Ready' : 'Unavailable'}
                            detail={agentsStatus.supabase_configured
                              ? 'Supabase is configured for user-scoped pipeline data.'
                              : 'Runtime controls and pipeline execution require Supabase storage.'}
                            tone={agentsStatus.supabase_configured ? 'ready' : 'warning'}
                          />
                          <EditorialStatus
                            label="OpenAI"
                            value={agentsStatus.openai_configured ? 'Ready' : 'Unavailable'}
                            detail={agentsStatus.openai_configured
                              ? 'Models are configured for scout and reviewer work.'
                              : 'The pipeline will skip runs until an API key is configured.'}
                            tone={agentsStatus.openai_configured ? 'ready' : 'warning'}
                          />
                          <EditorialStatus
                            label="Worker"
                            value={agentsStatus.worker_ready ? 'Ready' : 'Not ready'}
                            detail="The in-process worker accepts queued pipeline and lookup work."
                            tone={agentsStatus.worker_ready ? 'ready' : 'warning'}
                          />
                          <EditorialStatus
                            label="Pipeline"
                            value={agentsStatus.agents_will_run ? 'Able to run' : 'Blocked'}
                            detail={agentsStatus.thesis_error
                              ?? (agentsStatus.agents_will_run
                                ? 'Storage, model access, and thesis gates currently pass.'
                                : 'One or more required runtime gates are not ready.')}
                            tone={agentsStatus.agents_will_run ? 'ready' : 'warning'}
                          />
                        </div>
                      ) : (
                        <div className="py-phi-3">
                          <p className="type-body-sm text-oxford">Status unavailable</p>
                          <p className="mt-phi-2 type-note leading-relaxed text-oxford/60">
                            Aethria could not read the agent status endpoint. Runtime switch values above still reflect saved settings.
                          </p>
                        </div>
                      )}
                    </SettingsSection>
                  </>
                )}
              </div>
            </div>
          </div>
            </div>
          </div>
        </div>
      </main>
      <FundThesisConfirmationModal
        open={thesisConfirmation != null}
        changes={thesisConfirmation?.changes ?? []}
        firstPublication={thesisConfirmation?.firstPublication ?? false}
        busy={saving}
        onCancel={() => setThesisConfirmation(null)}
        onConfirm={confirmThesisDeployment}
      />
    </div>
  );
}
