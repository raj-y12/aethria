import { useEffect, useMemo, useState, type CSSProperties } from 'react';
import { Link, useNavigate } from 'react-router';
import { useClerk } from '@clerk/react-router';
import { UserProfile } from '@clerk/react';
import { useQueryClient } from '@tanstack/react-query';
import MobileHeader from '../components/MobileHeader';
import LoadingAnimation from '../components/LoadingAnimation';
import AgentLogoutModal from '../components/AgentLogoutModal';
import { fetchSettings, patchSettings, type Settings } from '../api/settings';
import { fetchMe } from '../api/me';
import { fetchAgentsStatus, toggleAgents, type AgentsStatus } from '../api/agents';
import {
  fetchFundThesisSummary,
  postFundThesisVersion,
  type FundThesisSummary,
} from '../api/fundThesis';
import { railEditorial } from '../design-system/railEditorial';
import { userProfileAppearance } from '../design-system/clerk-appearance';
import { useAgentsEnabled, useFundConfiguration, useMediaQuery } from '../hooks';
import {
  DEFAULT_SCORE_BANDS,
  bandForScore,
  clearFundConfiguration,
  computeConfiguredScore,
  getWeightImpactText,
  mapFundConfigToSettings,
  normalizeWeights,
  validateScoreBands,
  validateWeights,
  type DecisionLabel,
  type FundConfiguration,
  type MemoStyle,
  type MemoTone,
  type RiskSensitivity,
  type RubricCriterion,
  type ScoringDimensionKey,
} from '../lib/fundConfiguration';

type SectionId =
  | 'mandate'
  | 'weights'
  | 'bands'
  | 'thresholds'
  | 'risk'
  | 'memo'
  | 'rubric'
  | 'budget'
  | 'account';

const SELECT_CHEVRON =
  "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='10' viewBox='0 0 10 10'%3E%3Cpath fill='%231a2b48' fill-opacity='0.45' d='M0 3h10L5 8z'/%3E%3C/svg%3E\")";

const selectStyle: CSSProperties = { backgroundImage: SELECT_CHEVRON };

const sections: Array<{ id: SectionId; label: string; short: string }> = [
  { id: 'mandate', label: 'Fund Mandate', short: 'Mandate' },
  { id: 'weights', label: 'Scoring Weights', short: 'Weights' },
  { id: 'bands', label: 'Score Bands', short: 'Bands' },
  { id: 'thresholds', label: 'Decision Thresholds', short: 'Thresholds' },
  { id: 'risk', label: 'Adverse / Risk', short: 'Risk' },
  { id: 'memo', label: 'Memo Output', short: 'Memo' },
  { id: 'rubric', label: 'Rubric Criteria', short: 'Rubric' },
  { id: 'budget', label: 'Operations', short: 'Ops' },
  { id: 'account', label: 'Account', short: 'Account' },
];

const stageOptions = ['Pre-seed', 'Seed', 'Series A', 'Series B+'];
const geographyOptions = ['US', 'Europe', 'UK/Ireland', 'Global'];
const sectorOptions = ['B2B SaaS', 'AI', 'Infrastructure', 'Fintech', 'Healthcare', 'Devtools', 'Climate'];
const decisionLabels: DecisionLabel[] = ['Pass', 'Monitor', 'Review', 'Escalate', 'Strong Proceed'];

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
  const { lastSavedAt, ...rest } = config;
  return JSON.stringify(rest);
}

function serializeOperations(settings: Settings | null): string {
  if (!settings) return '';
  return JSON.stringify({
    agent_config: settings.agent_config,
    cost_budget: settings.cost_budget,
  });
}

function TextField({
  id,
  label,
  value,
  onChange,
  hint,
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
        onChange={(event) => onChange(type === 'number' ? Number(event.target.value) || 0 : event.target.value)}
        className={inputCls}
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
              className={`type-meta min-h-[38px] rounded-none px-phi-3 transition-colors ${active ? 'bg-oxford text-paper' : 'bg-oxford/[0.045] text-oxford/58 hover:bg-oxford/[0.075]'}`}
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
  const sample = useMemo(() => ({
    id: 'sample',
    scout: {
      id: 'sample-scout',
      scout_type: 'Preview',
      name: 'Sample Infrastructure AI Co.',
      one_line: 'Automates compliance-heavy engineering workflows for regulated teams.',
      sector: 'AI / Infrastructure',
      why_now: 'Regulatory burden and AI-native engineering stacks are converging.',
      confidence: 0.72,
      funding_stage: 'Seed',
    },
    review: {
      market_score: 8,
      product_score: 7,
      technical_score: 8,
      execution_score: 7,
      defensibility_score: 6,
      thesis_alignment_score: 0.78,
      thesis_matches_fund: true,
      key_risks: ['Early traction remains narrow.'],
    },
    timestamps: { discovered_at: new Date().toISOString() },
  }), []);
  const score = computeConfiguredScore(sample, config);
  const band = bandForScore(score, config.scoreBands);
  const weightTotal = validateWeights(config.scoringWeights).total;
  return (
    <aside className="hidden min-h-0 border-l border-oxford/[0.08] pl-phi-5 xl:flex xl:flex-col">
      <p className="type-label-section text-oxford/55">Configuration Preview</p>
      <div className="mt-phi-5 flex flex-col gap-phi-5">
        <div>
          <p className="type-meta text-oxford/35">Mandate</p>
          <p className="mt-phi-2 type-body-emphasis text-oxford">{config.mandate.fundName || 'Unnamed fund'}</p>
          <p className="mt-phi-1 type-body-sm text-oxford/52">
            {[...config.mandate.preferredStages, ...config.mandate.geographies].filter(Boolean).join(' / ') || 'No mandate scope set'}
          </p>
        </div>
        <div className="border-t border-oxford/[0.06] pt-phi-4">
          <p className="type-meta text-oxford/35">Total scoring weight</p>
          <p className={`mt-phi-2 font-mono text-[1.65rem] tabular-nums ${weightTotal === 100 ? 'text-oxford' : 'text-escalation/75'}`}>{weightTotal}%</p>
        </div>
        <div className="border-t border-oxford/[0.06] pt-phi-4">
          <p className="type-meta text-oxford/35">Decision bands</p>
          <div className="mt-phi-3 flex flex-col gap-phi-2">
            {config.scoreBands.map((item) => (
              <p key={item.id} className="type-meta text-oxford/52">
                <span className="font-mono tabular-nums">{item.min}-{item.max}</span> {item.label}
              </p>
            ))}
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
          <p className="mt-phi-2 type-body-emphasis text-oxford">{band.label}</p>
          <p className="mt-phi-1 type-body-sm text-oxford/55">
            Weighted score <span className="font-mono tabular-nums">{score}</span>. Current settings would route this company as {band.label.toLowerCase()}.
          </p>
        </div>
      </div>
    </aside>
  );
}

function buildThesisText(config: FundConfiguration): string {
  const mandate = config.mandate;
  return [
    `Fund: ${mandate.fundName || 'Unnamed fund'}`,
    `Mandate: ${mandate.mandateName}`,
    `Stages: ${mandate.preferredStages.join(', ') || 'Not specified'}`,
    `Geographies: ${[...mandate.geographies, mandate.customGeography].filter(Boolean).join(', ') || 'Not specified'}`,
    `Sectors: ${[...mandate.sectors, mandate.customSectors].filter(Boolean).join(', ') || 'Not specified'}`,
    `Excluded sectors: ${mandate.excludedSectors || 'None specified'}`,
    `Business models: ${mandate.businessModels || 'Not specified'}`,
    `Check size: ${mandate.checkSizeMin}-${mandate.checkSizeMax}`,
    `Ownership target: ${mandate.ownershipTarget}%`,
    `Minimum traction: ${mandate.minimumTraction || 'Not specified'}`,
    '',
    mandate.thesisText,
  ].join('\n');
}

export default function SettingsPage() {
  const navigate = useNavigate();
  const { signOut } = useClerk();
  const queryClient = useQueryClient();
  const isDesktop = useMediaQuery('(min-width: 1024px)');
  const agentsEnabled = useAgentsEnabled();

  const [settings, setSettings] = useState<Settings | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [errors, setErrors] = useState<string[]>([]);
  const [activeSection, setActiveSection] = useState<SectionId>('mandate');
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [showLogoutModal, setShowLogoutModal] = useState(false);
  const [userId, setUserId] = useState<string | null>(null);
  const [userIdCopied, setUserIdCopied] = useState(false);
  const [agentsStatus, setAgentsStatus] = useState<AgentsStatus | null>(null);
  const [thesisSummary, setThesisSummary] = useState<FundThesisSummary | null>(null);
  const [thesisBusy, setThesisBusy] = useState(false);
  const [savedSnapshot, setSavedSnapshot] = useState('');
  const [savedOperationsSnapshot, setSavedOperationsSnapshot] = useState('');

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
    fetchMe().then((me) => { if (!cancelled && me) setUserId(me.user_id); }).catch(() => undefined);
    fetchAgentsStatus().then((data) => { if (!cancelled) setAgentsStatus(data ?? null); }).catch(() => undefined);
    fetchFundThesisSummary().then((data) => { if (!cancelled) setThesisSummary(data); }).catch(() => undefined);
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    setDraft(configuration);
    setSavedSnapshot(serializeConfig(configuration));
  }, [configuration]);

  const weightValidation = useMemo(() => validateWeights(draft.scoringWeights), [draft.scoringWeights]);
  const bandValidation = useMemo(() => validateScoreBands(draft.scoreBands), [draft.scoreBands]);
  const unsaved = serializeConfig(draft) !== savedSnapshot || serializeOperations(settings) !== savedOperationsSnapshot;

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
    setStatus('Saved. Runtime limits and backend-compatible fund fields are synced; display-only memo and rubric options remain available in the app.');
    setSaving(false);
  };

  const handleReset = () => {
    const next = clearFundConfiguration(settings);
    setConfiguration(next);
    setDraft(next);
    setSavedSnapshot(serializeConfig(next));
    setStatus('Defaults restored locally. Save to sync backend-compatible fields.');
    setErrors([]);
  };

  const publishThesis = async () => {
    setThesisBusy(true);
    setErrors([]);
    try {
      await postFundThesisVersion(buildThesisText(draft).trim());
      const summary = await fetchFundThesisSummary();
      setThesisSummary(summary);
      setStatus('Mandate published as a fund thesis version.');
    } catch (error: unknown) {
      setErrors([error instanceof Error ? error.message : 'Could not publish thesis']);
    } finally {
      setThesisBusy(false);
    }
  };

  const doLogout = () => {
    localStorage.removeItem('aethria_last_activity');
    sessionStorage.removeItem('auth');
    sessionStorage.removeItem('authUser');
    signOut?.().then(() => navigate('/sign-in', { replace: true }));
  };

  const handleTurnOffAndLogout = async () => { await toggleAgents(false); doLogout(); };
  const handleTurnOnAndLogout = async () => { await toggleAgents(true); doLogout(); };
  const displayName = typeof sessionStorage !== 'undefined' ? sessionStorage.getItem('authUser') : null;

  if (loading) return <LoadingAnimation />;

  if (!settings) {
    return (
      <div className="flex h-[100dvh] flex-col overflow-hidden bg-paper">
        <main className="flex min-h-0 flex-1 items-center justify-center">
          <div>
            <p className={sectionLabelCls}>Settings unavailable</p>
            <p className="mt-phi-2 type-body-sm text-oxford/45">{loadError ?? 'The settings API did not return a payload.'}</p>
          </div>
        </main>
      </div>
    );
  }

  const mobileMenu = mobileMenuOpen ? (
    <section className="border-b border-hairline bg-oxford px-phi-4 py-phi-3" aria-label="Menu">
      <div className="flex flex-col items-start gap-phi-3">
        <Link to="/v1" className="type-label-section text-white/70" onClick={() => setMobileMenuOpen(false)}>Overview</Link>
        {displayName && <span className="type-label-section text-white/55">{displayName}</span>}
        <button type="button" onClick={() => setShowLogoutModal(true)} className="type-label-section text-white/55">Log out</button>
      </div>
    </section>
  ) : null;

  return (
    <div className="flex h-[100dvh] flex-col overflow-hidden bg-paper text-oxford">
      {!isDesktop && (
        <>
          <MobileHeader onMenuToggle={() => setMobileMenuOpen((open) => !open)} />
          {mobileMenu}
        </>
      )}

      <main className="flex min-h-0 flex-1 overflow-hidden bg-paper">
        <div className="w-3 shrink-0 self-stretch bg-oxford sm:w-6 md:w-10" aria-hidden />

        <aside className="hidden w-[18rem] shrink-0 flex-col border-r border-oxford/[0.08] px-phi-5 py-phi-5 lg:flex">
          <div className="pb-phi-6">
            <Link
              to="/v1"
              className={`${railEditorial.wordmark} block hover:opacity-80 transition-opacity btn-interaction`}
              aria-label="Aethria — return to workspace"
            >
              Aethria
            </Link>
            <Link
              to="/v1"
              className="type-meta mt-phi-2 inline-flex min-h-[44px] items-center uppercase text-oxford/35 transition-colors hover:text-oxford/60 btn-interaction"
            >
              Return to conviction workspace
            </Link>
          </div>
          <p className="type-label-section text-oxford/45">Fund Configuration</p>
          <nav className="mt-phi-5 flex flex-col gap-phi-1" aria-label="Settings sections">
            {sections.map((section) => (
              <a
                key={section.id}
                href={`#${section.id}`}
                onClick={() => setActiveSection(section.id)}
                className={`type-label-tab min-h-[36px] px-phi-3 py-phi-2 transition-colors ${activeSection === section.id ? 'bg-oxford/[0.055] text-oxford' : 'text-oxford/40 hover:bg-oxford/[0.03] hover:text-oxford/70'}`}
              >
                {section.short}
              </a>
            ))}
          </nav>
          <div className="mt-auto border-t border-oxford/[0.08] pt-phi-5">
            <p className="type-meta text-oxford/38">
              {unsaved ? 'Unsaved changes' : draft.lastSavedAt ? `Last saved ${new Date(draft.lastSavedAt).toLocaleString()}` : 'Not saved yet'}
            </p>
            <div className="mt-phi-3 flex items-center gap-phi-4">
              <button type="button" onClick={handleSave} disabled={saving} className={solidBtnCls}>
                {saving ? 'Saving...' : 'Save changes'}
              </button>
              <button type="button" onClick={handleReset} className={actionBtnCls}>Reset</button>
            </div>
          </div>
        </aside>

        <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
          <div className="flex items-center justify-between border-b border-oxford/[0.08] px-phi-5 py-phi-4 lg:hidden">
            <div>
              <p className={sectionLabelCls}>Fund Configuration</p>
              <Link to="/v1" className="mt-phi-1 inline-flex type-meta text-oxford/38 transition-colors hover:text-oxford">
                {unsaved ? 'Unsaved changes' : 'Return to workspace'}
              </Link>
            </div>
            <button type="button" onClick={handleSave} disabled={saving} className={solidBtnCls}>
              {saving ? 'Saving...' : 'Save'}
            </button>
          </div>

          <div className="min-h-0 flex-1 overflow-y-auto px-phi-5 py-phi-6 lg:px-phi-7">
            <div className="grid min-h-full gap-phi-7 xl:grid-cols-[minmax(0,1fr)_18rem]">
              <div className="min-w-0">
                <header className="mb-phi-7 max-w-[54rem]">
                  <p className="type-label-section text-oxford/45">{draft.versionLabel}</p>
                  <h1 className="mt-phi-3 font-display text-[2.2rem] font-medium leading-[0.98] tracking-0 text-oxford sm:text-[3rem]">
                    How this fund thinks
                  </h1>
                  <p className="mt-phi-4 max-w-[42rem] type-body leading-relaxed text-oxford/58">
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
                      <button type="button" onClick={publishThesis} disabled={thesisBusy || !agentsStatus?.supabase_configured} className={actionBtnCls}>
                        {thesisBusy ? 'Publishing...' : 'Publish fund thesis version'}
                      </button>
                      <p className="type-meta text-oxford/38">
                        {thesisSummary ? `Active thesis v${thesisSummary.active_version_number}` : 'No active thesis loaded'}
                      </p>
                    </div>
                  </div>
                </SettingsSection>

                <SettingsSection id="weights" title="Scoring Weights" kicker="Weights match the five reviewer dimensions used by deterministic backend scoring. Traction and timing remain sub-signals inside Execution and Market.">
                  <div className="flex flex-col gap-phi-4">
                    <div className="flex flex-wrap items-center justify-between gap-phi-4 border-b border-oxford/[0.06] pb-phi-4">
                      <p className={`font-mono text-[1.6rem] tabular-nums ${weightValidation.valid ? 'text-oxford' : 'text-escalation/75'}`}>{weightValidation.total}%</p>
                      <div className="flex items-center gap-phi-4">
                        {!weightValidation.valid && <p className="type-meta text-escalation/70">Adjust by {weightValidation.delta}%</p>}
                        <button type="button" onClick={() => updateDraft((current) => ({ ...current, scoringWeights: normalizeWeights(current.scoringWeights) }))} className={actionBtnCls}>
                          Normalize to 100
                        </button>
                      </div>
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
                            scoringWeights: current.scoringWeights.map((weight) => weight.key === item.key ? { ...weight, weight: Number(event.target.value) || 0 } : weight),
                          }))}
                          className={`${inputCls} text-right font-mono tabular-nums`}
                          aria-label={`${item.label} weight`}
                        />
                      </div>
                    ))}
                  </div>
                </SettingsSection>

                <SettingsSection id="bands" title="Score Bands" kicker="Bands convert raw configured scores into recommendation language and queue priority. Boundaries must be continuous and non-overlapping.">
                  <div className="flex flex-col gap-phi-4">
                    {!bandValidation.valid && (
                      <div className="border border-escalation/25 bg-escalation/[0.035] px-phi-4 py-phi-3">
                        {bandValidation.errors.map((error) => <p key={error} className="type-body-sm text-escalation/75">{error}</p>)}
                      </div>
                    )}
                    {draft.scoreBands.map((band) => (
                      <div key={band.id} className="grid gap-phi-3 border-b border-oxford/[0.055] py-phi-4 sm:grid-cols-[1fr_86px_86px_150px] sm:items-end">
                        <p className="type-body-emphasis text-oxford">{band.label}</p>
                        <TextField id={`${band.id}-min`} label="Min" type="number" value={band.min} onChange={(value) => updateDraft((current) => ({ ...current, scoreBands: current.scoreBands.map((item) => item.id === band.id ? { ...item, min: Number(value) } : item) }))} min={0} max={100} />
                        <TextField id={`${band.id}-max`} label="Max" type="number" value={band.max} onChange={(value) => updateDraft((current) => ({ ...current, scoreBands: current.scoreBands.map((item) => item.id === band.id ? { ...item, max: Number(value) } : item) }))} min={0} max={100} />
                        <div className="flex flex-col gap-phi-2">
                          <label htmlFor={`${band.id}-label`} className={labelCls}>Decision label</label>
                          <select
                            id={`${band.id}-label`}
                            value={band.label}
                            onChange={(event) => updateDraft((current) => ({ ...current, scoreBands: current.scoreBands.map((item) => item.id === band.id ? { ...item, label: event.target.value as DecisionLabel } : item) }))}
                            className={selectCls}
                            style={selectStyle}
                          >
                            {decisionLabels.map((label) => <option key={label} value={label}>{label}</option>)}
                          </select>
                        </div>
                      </div>
                    ))}
                    <button type="button" onClick={() => updateDraft((current) => ({ ...current, scoreBands: DEFAULT_SCORE_BANDS }))} className={actionBtnCls}>
                      Restore default bands
                    </button>
                  </div>
                </SettingsSection>

                <SettingsSection id="thresholds" title="Decision Thresholds" kicker="Thresholds shape app routing, stale detection, and recommendation language. Partner rules still come from versioned backend policy.">
                  <div className="grid gap-phi-5 md:grid-cols-2">
                    <TextField id="auto-pass" label="Auto-pass threshold" type="number" value={draft.thresholds.autoPass} onChange={(value) => updateThreshold('autoPass', Number(value))} min={0} max={100} />
                    <TextField id="monitor-threshold" label="Monitor threshold" type="number" value={draft.thresholds.monitor} onChange={(value) => updateThreshold('monitor', Number(value))} min={0} max={100} />
                    <TextField id="escalation-threshold" label="Escalation threshold" type="number" value={draft.thresholds.escalation} onChange={(value) => updateThreshold('escalation', Number(value))} min={0} max={100} />
                    <TextField id="partner-review-threshold" label="Partner-review threshold" type="number" value={draft.thresholds.partnerReview} onChange={(value) => updateThreshold('partnerReview', Number(value))} min={0} max={100} />
                    <TextField id="stale-after" label="Stale after hours" type="number" value={draft.thresholds.staleAfterHours} onChange={(value) => updateThreshold('staleAfterHours', Number(value))} min={1} />
                    <TextField id="confidence-floor" label="Confidence floor" type="number" step={0.01} value={draft.thresholds.confidenceFloor} onChange={(value) => updateThreshold('confidenceFloor', Number(value))} min={0} max={1} />
                    <TextField id="missing-data-threshold" label="Missing-data threshold" type="number" value={draft.thresholds.missingDataThreshold} onChange={(value) => updateThreshold('missingDataThreshold', Number(value))} min={0} max={100} />
                  </div>
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
                      <ToggleRow id="risk-ack" checked={draft.risk.requireAcknowledgement} onChange={(value) => updateRisk('requireAcknowledgement', value)} label="Require risk acknowledgement before ruling" hint="When enabled, high-risk pending deals require a reviewed-risk interaction before Commit ruling." />
                      <ToggleRow id="risk-high-only" checked={draft.risk.onlyGateHighSeverity} onChange={(value) => updateRisk('onlyGateHighSeverity', value)} label="Only gate high severity risks" hint="Power users can leave medium adverse items visible without slowing the ruling action." />
                    </div>
                    <div className="grid gap-phi-5 md:grid-cols-2">
                      <TextField id="founder-penalty" label="Missing founder/team data penalty" type="number" value={draft.risk.missingFounderPenalty} onChange={(value) => updateRisk('missingFounderPenalty', Number(value))} min={0} max={100} />
                      <TextField id="traction-penalty" label="Missing traction data penalty" type="number" value={draft.risk.missingTractionPenalty} onChange={(value) => updateRisk('missingTractionPenalty', Number(value))} min={0} max={100} />
                      <TextField id="contradiction-penalty" label="Contradiction penalty" type="number" value={draft.risk.contradictionPenalty} onChange={(value) => updateRisk('contradictionPenalty', Number(value))} min={0} max={100} />
                      <TextField id="weak-source-penalty" label="Weak-source penalty" type="number" value={draft.risk.weakSourcePenalty} onChange={(value) => updateRisk('weakSourcePenalty', Number(value))} min={0} max={100} />
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

                <SettingsSection id="rubric" title="Rubric Criteria Editor" kicker="Save display criteria for local rationale previews and future policy work. Current backend scoring uses the five core dimensions and versioned policy files.">
                  <div className="flex flex-col gap-phi-5">
                    {draft.rubric.map((criterion) => (
                      <div key={criterion.id} className="border-t border-oxford/[0.06] pt-phi-5 first:border-t-0 first:pt-0">
                        <div className="grid gap-phi-5 md:grid-cols-[1fr_160px_90px]">
                          <TextField id={`${criterion.id}-name`} label="Criterion name" value={criterion.name} onChange={(value) => updateDraft((current) => ({ ...current, rubric: updateCriterion(current.rubric, criterion.id, { name: String(value) }) }))} />
                          <div className="flex flex-col gap-phi-2">
                            <label htmlFor={`${criterion.id}-dimension`} className={labelCls}>Dimension</label>
                            <select id={`${criterion.id}-dimension`} value={criterion.dimension} onChange={(event) => updateDraft((current) => ({ ...current, rubric: updateCriterion(current.rubric, criterion.id, { dimension: event.target.value as ScoringDimensionKey }) }))} className={selectCls} style={selectStyle}>
                              {draft.scoringWeights.map((item) => <option key={item.key} value={item.key}>{item.label}</option>)}
                            </select>
                          </div>
                          <TextField id={`${criterion.id}-weight`} label="Weight" type="number" value={criterion.weight} onChange={(value) => updateDraft((current) => ({ ...current, rubric: updateCriterion(current.rubric, criterion.id, { weight: Number(value) }) }))} min={0} max={100} />
                        </div>
                        <div className="mt-phi-4 grid gap-phi-4">
                          <TextAreaField id={`${criterion.id}-description`} label="Description" rows={2} value={criterion.description} onChange={(value) => updateDraft((current) => ({ ...current, rubric: updateCriterion(current.rubric, criterion.id, { description: value }) }))} />
                          <div className="grid gap-phi-4 md:grid-cols-2">
                            <TextAreaField id={`${criterion.id}-positive`} label="Positive signals" rows={2} value={criterion.positiveSignals} onChange={(value) => updateDraft((current) => ({ ...current, rubric: updateCriterion(current.rubric, criterion.id, { positiveSignals: value }) }))} />
                            <TextAreaField id={`${criterion.id}-negative`} label="Negative signals" rows={2} value={criterion.negativeSignals} onChange={(value) => updateDraft((current) => ({ ...current, rubric: updateCriterion(current.rubric, criterion.id, { negativeSignals: value }) }))} />
                          </div>
                          <TextField id={`${criterion.id}-missing`} label="Missing-data behavior" value={criterion.missingDataBehavior} onChange={(value) => updateDraft((current) => ({ ...current, rubric: updateCriterion(current.rubric, criterion.id, { missingDataBehavior: String(value) }) }))} />
                          <div className="grid gap-phi-4 md:grid-cols-4">
                            {(['score3', 'score5', 'score7', 'score9'] as const).map((scoreKey) => (
                              <TextAreaField
                                key={scoreKey}
                                id={`${criterion.id}-${scoreKey}`}
                                label={scoreKey.replace('score', 'Earns ')}
                                rows={2}
                                value={criterion.examples[scoreKey]}
                                onChange={(value) => updateDraft((current) => ({ ...current, rubric: updateCriterion(current.rubric, criterion.id, { examples: { ...criterion.examples, [scoreKey]: value } }) }))}
                              />
                            ))}
                          </div>
                          <button type="button" onClick={() => updateDraft((current) => ({ ...current, rubric: current.rubric.filter((item) => item.id !== criterion.id) }))} className={`${actionBtnCls} self-start`}>
                            Remove criterion
                          </button>
                        </div>
                      </div>
                    ))}
                    <button
                      type="button"
                      onClick={() => updateDraft((current) => ({ ...current, rubric: [...current.rubric, newCriterion(current.scoringWeights[0]?.key ?? 'market')] }))}
                      className={`${solidBtnCls} self-start`}
                    >
                      Add criterion
                    </button>
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

                <SettingsSection id="account" title="Account" kicker="Identity and local operator details.">
                  <div className="flex flex-col gap-phi-5">
                    <div className="aethria-clerk-profile min-h-[320px]">
                      <UserProfile appearance={userProfileAppearance} routing="hash" />
                    </div>
                    {userId && (
                      <div className="border-t border-oxford/[0.06] pt-phi-4">
                        <p className={labelCls}>User ID</p>
                        <div className="mt-phi-3 flex flex-wrap items-center gap-phi-3">
                          <code className="type-meta bg-oxford/[0.05] px-phi-3 py-phi-2 text-oxford/55" aria-hidden>{userId.replace(/./g, '*')}</code>
                          <button type="button" onClick={() => navigator.clipboard?.writeText(userId).then(() => { setUserIdCopied(true); setTimeout(() => setUserIdCopied(false), 2000); })} className={actionBtnCls}>
                            {userIdCopied ? 'Copied' : 'Copy'}
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                </SettingsSection>
              </div>

              <PreviewPanel config={draft} />
            </div>
          </div>
        </div>
      </main>

      <AgentLogoutModal
        open={showLogoutModal}
        agentsEnabled={agentsEnabled}
        onCancel={() => setShowLogoutModal(false)}
        onKeepRunning={() => { setShowLogoutModal(false); doLogout(); }}
        onTurnOffAndLogout={handleTurnOffAndLogout}
        onTurnOnAndLogout={handleTurnOnAndLogout}
      />
    </div>
  );
}

function updateCriterion(
  rubric: RubricCriterion[],
  id: string,
  patch: Partial<RubricCriterion>
): RubricCriterion[] {
  return rubric.map((item) => item.id === id ? { ...item, ...patch } : item);
}

function newCriterion(dimension: ScoringDimensionKey): RubricCriterion {
  const id = `criterion-${Date.now()}`;
  return {
    id,
    dimension,
    name: 'New criterion',
    description: '',
    weight: 25,
    positiveSignals: '',
    negativeSignals: '',
    missingDataBehavior: 'Reduce confidence until evidence is supplied.',
    examples: {
      score3: '',
      score5: '',
      score7: '',
      score9: '',
    },
  };
}
