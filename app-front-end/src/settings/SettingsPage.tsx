import { useEffect, useMemo, useRef, useState, type CSSProperties } from 'react';
import { useNavigate } from 'react-router';
import { motion } from 'framer-motion';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import LoadingAnimation from '../components/LoadingAnimation';
import { workspaceLayout } from '../design-system/workspaceLayout';
import { getQueryConfig } from '../lib/queryIntent';
import { fetchSettings, patchSettings, publishPolicy, type Settings } from '../api/settings';
import { fetchAgentsStatus, type AgentsStatus } from '../api/agents';
import {
  fetchFundThesisSummary,
  type FundThesisSummary,
} from '../api/fundThesis';
import { useFundConfiguration, usePrefersReducedMotion } from '../hooks';
import DecisionThresholdsPanel from './DecisionThresholdsPanel';
import FundThesisConfirmationModal from './FundThesisConfirmationModal';
import SettingsTopBar from './SettingsTopBar';
import SettingsRail from './SettingsRail';
import SettingsMobileNav from './SettingsMobileNav';
import OperationsStrip from './OperationsStrip';
import { validateDecisionThresholds } from '../lib/decisionThresholds';
import {
  getDeploymentConfirmation,
  getPendingChanges,
  serializeDecisionConfig,
  SETTINGS_SECTIONS,
  type PendingChange,
  type FundThesisChangeSet,
  type SectionId,
} from './settingsModel';

const CONTENT_EASE = [0.16, 1, 0.3, 1] as const;
import {
  applyThesisVersionMetadata,
  clearFundConfiguration,
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
    <section id={id} className={`flex min-w-0 scroll-mt-16 flex-col gap-phi-4 px-phi-4 pb-phi-5 pt-phi-5 lg:scroll-mt-0 ${className ?? ''}`}>
      <div>
        <div className="flex flex-wrap items-baseline justify-between gap-x-phi-4 gap-y-phi-1">
          <h2 className={sectionLabelCls}>{title}</h2>
          {label ? <span className="type-label-section text-oxford/45">{label}</span> : null}
        </div>
        {description ? (
          <p className="mt-phi-2 max-w-[42rem] type-body-sm leading-relaxed text-oxford/60">{description}</p>
        ) : null}
      </div>
      <div className="min-w-0">{children}</div>
    </section>
  );
}

function SpecRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid gap-phi-3 border-t border-oxford/[0.06] py-phi-4 sm:grid-cols-[clamp(110px,18%,160px)_minmax(0,1fr)] sm:items-start sm:gap-phi-5">
      <p className="type-label-section pt-phi-2 text-oxford/55">{label}</p>
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
    <div className="grid gap-x-phi-4 gap-y-phi-1 border-b border-oxford/[0.05] py-phi-3 last:border-b-0 sm:grid-cols-[minmax(6rem,32%)_minmax(0,1fr)] sm:items-baseline">
      <p className="type-label-section text-oxford/65">{label}</p>
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
    <div className="px-phi-4 pb-phi-3 pt-phi-7">
      <h2 className="type-display text-[1.5rem] leading-none text-oxford">{title}</h2>
      <p className="mt-phi-2 type-body-sm text-oxford/60">{description}</p>
    </div>
  );
}

export default function SettingsPage() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const reduceMotion = usePrefersReducedMotion();

  const [settings, setSettings] = useState<Settings | null>(null);
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [errors, setErrors] = useState<string[]>([]);
  const [thesisConfirmation, setThesisConfirmation] = useState<FundThesisChangeSet | null>(null);
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

  const weightValidation = useMemo(() => validateWeights(draft.scoringWeights), [draft.scoringWeights]);
  const bandValidation = useMemo(() => validateScoreBands(draft.scoreBands), [draft.scoreBands]);
  const thresholdValidation = useMemo(() => validateDecisionThresholds(draft), [draft]);
  const attentionSection: SectionId | null = !bandValidation.valid || !thresholdValidation.valid
    ? 'thresholds'
    : !weightValidation.valid
      ? 'weights'
      : null;

  // Draft vs Live only covers deployable decision configuration. Runtime
  // controls save independently in OperationsStrip and never enter this list.
  const pendingChanges = useMemo<PendingChange[]>(
    () => getPendingChanges(draft, savedSnapshot),
    [draft, savedSnapshot],
  );
  const storageNotReady = agentsStatus != null && !agentsStatus.supabase_configured;

  // Clicking a rail item scrolls its section to the top of the reading column.
  // The scroll-spy observer below then confirms the active state from what's
  // actually on screen, so a click and a manual scroll converge on one source.
  const scrollToSection = (id: SectionId) => {
    setActiveSection(id);
    const target = contentScrollRef.current?.querySelector<HTMLElement>(`#${id}`);
    target?.scrollIntoView({ behavior: reduceMotion ? 'auto' : 'smooth', block: 'start' });
  };

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
          <div>
            <p className={sectionLabelCls}>Settings unavailable</p>
            <p className="mt-phi-2 type-body-sm text-oxford/60">The settings API did not return a payload.</p>
          </div>
        </main>
      </div>
    );
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden bg-paper text-oxford">
      <SettingsTopBar
        live={pendingChanges.length === 0}
        pendingCount={pendingChanges.length}
        saving={saving}
        onBack={() => navigate('/v1')}
        onReset={handleReset}
        onDeploy={requestDeploy}
      />

      <div className="flex min-h-0 flex-1 overflow-hidden">
        <SettingsRail
          activeSection={activeSection}
          attentionSection={attentionSection}
          onNavigate={scrollToSection}
          settings={settings}
          storageUnavailable={storageNotReady}
          onSettingsChange={setSettings}
        />

        <div
          ref={contentScrollRef}
          className="min-h-0 flex-1 overflow-y-auto overscroll-contain bg-paper"
        >
          <SettingsMobileNav
            activeSection={activeSection}
            attentionSection={attentionSection}
            onSelect={scrollToSection}
          />
          <motion.main
            className={`${workspaceLayout.pageBottom} mx-auto w-full max-w-[52rem] px-phi-5 pt-phi-5 lg:px-phi-7`}
            initial={reduceMotion ? false : { opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, ease: CONTENT_EASE, delay: 0.16 }}
          >
            <div className="mb-phi-5 border border-oxford/[0.08] lg:hidden">
              <OperationsStrip
                variant="bar"
                settings={settings}
                storageUnavailable={storageNotReady}
                onSettingsChange={setSettings}
              />
            </div>

            {(status || errors.length > 0) && (
              <div className="mb-phi-4 border-b border-oxford/[0.08] pb-phi-3" role={errors.length ? 'alert' : 'status'}>
                {errors.length > 0 ? (
                  <ul className="flex flex-col gap-phi-1">
                    {errors.map((error) => <li key={error} className="type-body-sm text-escalation/75">{error}</li>)}
                  </ul>
                ) : (
                  <p className="type-body-sm text-oxford/60">{status}</p>
                )}
              </div>
            )}

            <div className="divide-y divide-oxford/[0.06]">
                  <GroupHeader
                    title="Fund policy"
                    description="Changes here stay in draft until you deploy a new version."
                  />

                  <RoomSection
                    id="thesis"
                    title="The mandate"
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
                        <ChipGroup label="Geographies" options={geographyOptions} selected={draft.mandate.geographies} onChange={(value) => updateMandate('geographies', value)} />
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
                        <TextField id="check-min" label="Check size min" type="number" value={draft.mandate.checkSizeMin} onChange={(value) => updateMandate('checkSizeMin', Number(value))} min={0} />
                        <TextField id="check-max" label="Check size max" type="number" value={draft.mandate.checkSizeMax} onChange={(value) => updateMandate('checkSizeMax', Number(value))} min={0} />
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

                {!bandValidation.valid && (
                  <div className="border-l-2 border-escalation/35 bg-escalation/[0.035] px-phi-4 py-phi-3">
                    {bandValidation.errors.map((error) => <p key={error} className="type-body-sm text-escalation/75">{error}</p>)}
                  </div>
                )}

                  <RoomSection
                    id="thresholds"
                    title="Decision mechanics"
                    label="Thresholds"
                    description="Drag the dividers to set where Pass, Monitor, and Invest begin."
                  >
                    <DecisionThresholdsPanel draft={draft} updateDraft={updateDraft} updateThreshold={updateThreshold} />
                  </RoomSection>

                  <RoomSection
                    id="sensitivity"
                    title="Escalation sensitivity"
                    label="Risk posture"
                  >
                    <div className="flex flex-col gap-phi-2 border-t border-oxford/[0.06] py-phi-4">
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
                    <div className="flex flex-wrap items-baseline justify-between gap-phi-4 border-t border-oxford/[0.06] py-phi-4">
                      <div className="flex items-baseline gap-phi-3">
                        <p className={`type-data text-[1.6rem] ${weightValidation.valid ? 'text-oxford' : 'text-escalation/75'}`}>{weightValidation.total}%</p>
                        <p className="type-label-section">Total weight</p>
                      </div>
                      <p className="type-note text-oxford/60">Adjust one — the rest rebalance to 100</p>
                    </div>
                    {draft.scoringWeights.map((item) => (
                      <div key={item.key} className="grid gap-phi-3 border-t border-oxford/[0.06] py-phi-4 md:grid-cols-[minmax(0,1fr)_92px] md:items-baseline">
                        <p className="type-body-emphasis text-oxford">{item.label}</p>
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
                    <p className="border-t border-oxford/[0.06] py-phi-4 type-note text-oxford/55">
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
                    <div className="grid gap-phi-5 border-t border-oxford/[0.06] py-phi-4 md:grid-cols-2">
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
                    title="Ruling workflow"
                    label="Governance"
                  >
                    <div className="border-t border-oxford/[0.06]">
                      <ToggleRow id="risk-ack" checked={draft.risk.requireAcknowledgement} onChange={(value) => updateRisk('requireAcknowledgement', value)} label="Require acknowledgement before ruling" hint="High-risk pending deals need a reviewed-risk step before Commit." />
                      <ToggleRow id="risk-high-only" checked={draft.risk.onlyGateHighSeverity} onChange={(value) => updateRisk('onlyGateHighSeverity', value)} label="Only gate high severity risks" hint="Medium adverse items stay visible without blocking the ruling." />
                    </div>
                  </RoomSection>

                  <GroupHeader
                    title="Live runtime"
                    description="Changes here save immediately and affect the running system."
                  />

                  <RoomSection
                    id="budget"
                    title="Cost budget"
                    label="Live limits"
                  >
                    <div className="grid gap-x-phi-8 sm:grid-cols-2">
                      <SpecRow label="Per run"><p className="type-data text-[1.35rem]">{settings.cost_budget.max_tokens_per_run.toLocaleString()} tokens</p></SpecRow>
                      <SpecRow label="Cooldown"><p className="type-data text-[1.35rem]">{settings.cost_budget.cooldown_seconds}s</p></SpecRow>
                      <SpecRow label="Daily"><p className="type-data text-[1.35rem]">${settings.cost_budget.daily_cost_ceiling.toLocaleString()}</p></SpecRow>
                      <SpecRow label="Weekly"><p className="type-data text-[1.35rem]">${settings.cost_budget.weekly_cost_ceiling.toLocaleString()}</p></SpecRow>
                    </div>
                    <p className="border-t border-oxford/[0.06] pt-phi-4 type-note text-oxford/55">Enforcement is {settings.cost_budget.enabled ? 'on' : 'off'} — toggle it in the rail.</p>
                  </RoomSection>

                  <RoomSection
                    id="system"
                    title="System state"
                    label="Run gates"
                  >
                    {agentsStatus ? (
                      <div className="border-t border-oxford/[0.06]">
                        <EditorialStatus
                          label="Storage"
                          value={agentsStatus.supabase_configured ? 'Ready' : 'Unavailable'}
                          detail={agentsStatus.supabase_configured ? undefined : 'Supabase required to run the pipeline.'}
                          tone={agentsStatus.supabase_configured ? 'ready' : 'warning'}
                        />
                        <EditorialStatus
                          label="OpenAI"
                          value={agentsStatus.openai_configured ? 'Ready' : 'Unavailable'}
                          detail={agentsStatus.openai_configured ? undefined : 'API key required to run the pipeline.'}
                          tone={agentsStatus.openai_configured ? 'ready' : 'warning'}
                        />
                        <EditorialStatus
                          label="Worker"
                          value={agentsStatus.worker_ready ? 'Ready' : 'Not ready'}
                          tone={agentsStatus.worker_ready ? 'ready' : 'warning'}
                        />
                        <EditorialStatus
                          label="Pipeline"
                          value={agentsStatus.agents_will_run ? 'Able to run' : 'Blocked'}
                          detail={agentsStatus.agents_will_run ? undefined : (agentsStatus.thesis_error ?? 'A required gate is not ready.')}
                          tone={agentsStatus.agents_will_run ? 'ready' : 'warning'}
                        />
                      </div>
                    ) : (
                      <div className="border-t border-oxford/[0.06] py-phi-4">
                        <p className="type-body-sm text-oxford">Status unavailable</p>
                        <p className="mt-phi-2 type-note leading-relaxed text-oxford/60">
                          Aethria could not read the agent status endpoint. Runtime switch values above still reflect saved settings.
                        </p>
                      </div>
                    )}
                  </RoomSection>
            </div>
          </motion.main>
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
    </div>
  );
}
