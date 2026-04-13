import { useState, useEffect, type ReactNode, type CSSProperties } from 'react';
import { Link, useNavigate } from 'react-router';
import { useClerk } from '@clerk/react-router';
import { UserProfile } from '@clerk/react';
import { motion, AnimatePresence } from 'framer-motion';
import SystemBar from '../components/SystemBar';
import MobileHeader from '../components/MobileHeader';
import PanelShell, { PANEL_TAB_BAR_CLASS } from '../components/PanelShell';
import LoadingAnimation from '../components/LoadingAnimation';
import { fetchSettings, patchSettings, type AgentBudgetStatus, type Settings, type FundIdentity } from '../api/settings';
import { fetchMe } from '../api/me';
import { fetchAgentsStatus, type AgentsStatus } from '../api/agents';
import {
  fetchFundThesisSummary,
  patchFundThesisActiveVersion,
  postFundThesisReprocessMissing,
  postFundThesisVersion,
  type FundThesisSummary,
} from '../api/fundThesis';
import { tokens } from '../design-system/tokens';
import { userProfileAppearance } from '../design-system/clerk-appearance';
import { transitionOrReduced } from '../design-system/motion';
import { useMediaQuery, usePrefersReducedMotion } from '../hooks';

type TabId = 'fund' | 'pipeline' | 'discovery' | 'portfolio' | 'budget' | 'account';

const FONT_SANS = '"Instrument Sans", system-ui, sans-serif' as const;

const SETTINGS_HEADER_LABEL_CLASS =
  'type-meta uppercase text-oxford/40';

const SETTINGS_SAVE_BTN_CLASS =
  `${SETTINGS_HEADER_LABEL_CLASS} rounded-none border-0 bg-transparent p-0 cursor-pointer hover:text-oxford/80 transition-colors duration-150 ease-out btn-interaction focus:outline-none focus-visible:ring-2 focus-visible:ring-oxford/40 focus-visible:ring-inset`;

const SETTINGS_TAB_NAV_CLASS = `${PANEL_TAB_BAR_CLASS} pt-phi-3 pb-0`;
const SETTINGS_TAB_BTN_CLASS =
  'py-phi-3 px-phi-4 type-label-tab border-b border-oxford/15 -mb-px focus:outline-none focus-visible:ring-2 focus-visible:ring-oxford/40 focus-visible:ring-inset btn-interaction transition-[border-color,color]';
const SETTINGS_TAB_ACTIVE_CLASS = 'border-oxford text-oxford';
const SETTINGS_TAB_INACTIVE_CLASS =
  'border-oxford/15 text-oxford/35 hover:border-oxford/35 hover:text-oxford/60';

const settingsDescClass =
  'max-w-xl leading-[1.6] m-0 text-[14px] font-normal text-oxford/70';

const settingsFieldLabelClass = 'text-[13px] font-normal text-oxford/70';

const settingsInputCls =
  'w-full min-w-0 max-w-[10rem] appearance-none bg-transparent border-0 border-b border-solid border-oxford/20 rounded-none shadow-none outline-none ring-0 focus:ring-0 focus:border-oxford/60 focus:outline-none transition-[border-color] duration-150 ease-out text-[14px] font-normal text-oxford/[0.85] py-[6px] px-0 placeholder:text-oxford/35 btn-interaction [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none [-moz-appearance:textfield]';

const SELECT_CHEVRON =
  "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='10' viewBox='0 0 10 10'%3E%3Cpath fill='%23002147' fill-opacity='0.5' d='M0 3h10L5 8z'/%3E%3C/svg%3E\")";

const selectCls =
  `${settingsInputCls} cursor-pointer max-w-full pr-8 bg-no-repeat bg-[length:10px] bg-[center_right_2px]`;

const settingsSelectStyle: CSSProperties = {
  fontFamily: FONT_SANS,
  backgroundImage: SELECT_CHEVRON,
};

const hintCls = `block mt-1 mb-0 ${settingsDescClass}`;

const TOGGLE_TRACK =
  'h-6 w-11 shrink-0 cursor-pointer inline-flex items-center overflow-hidden rounded-[3px]';
const TOGGLE_KNOB = 'h-4 w-4 rounded-[2px] pointer-events-none block';

function SettingSectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <div>
      <div className="type-label-section text-oxford/[0.58] mb-phi-3">
        {children}
      </div>
      <div className="h-px w-full bg-oxford/10 mb-phi-4" aria-hidden />
    </div>
  );
}

function DescText({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return (
    <p className={`${settingsDescClass} ${className}`} style={{ fontFamily: FONT_SANS }}>
      {children}
    </p>
  );
}

function SettingRow({
  label,
  hint,
  children,
  id,
}: { label: string; hint?: string; children: ReactNode; id?: string }) {
  return (
    <div className="grid grid-cols-[minmax(0,200px)_1fr] gap-x-6 gap-y-1 items-start">
      <div className="min-w-0">
        {id ? (
          <label htmlFor={id} className={settingsFieldLabelClass} style={{ fontFamily: FONT_SANS }}>
            {label}
          </label>
        ) : (
          <span className={settingsFieldLabelClass} style={{ fontFamily: FONT_SANS }}>
            {label}
          </span>
        )}
        {hint && (
          <div className={hintCls} style={{ fontFamily: FONT_SANS }}>
            {hint}
          </div>
        )}
      </div>
      <div className="min-w-0 flex items-center">{children}</div>
    </div>
  );
}

function Toggle({
  id,
  checked,
  onChange,
  label,
  hint,
}: { id: string; checked: boolean; onChange: (v: boolean) => void; label: string; hint?: string }) {
  return (
    <SettingRow id={id} label={label} hint={hint}>
      <button
        id={id}
        type="button"
        role="switch"
        aria-checked={checked}
        aria-label={label}
        onClick={() => onChange(!checked)}
        className={`relative shrink-0 ${TOGGLE_TRACK} btn-interaction focus-visible:ring-1 focus-visible:ring-oxford/25 focus-visible:ring-offset-2 focus-visible:ring-offset-paper ${
          checked ? 'bg-oxford' : 'bg-oxford/[0.06]'
        }`}
        style={{ transitionTimingFunction: tokens.motion.easeCss }}
      >
        <span
          className={`${TOGGLE_KNOB} ${checked ? 'translate-x-5 bg-paper' : 'translate-x-1 bg-oxford/40'}`}
          style={{
            transition: `transform var(--motion-short) var(--motion-ease), background-color var(--motion-micro) var(--motion-ease)`,
          }}
          aria-hidden
        />
      </button>
    </SettingRow>
  );
}

function Field({
  id,
  label,
  hint,
  value,
  onChange,
  type = 'number',
  min,
  step,
  inline,
}: {
  id: string;
  label: string;
  hint?: string;
  value: number | string;
  onChange: (v: number | string) => void;
  type?: 'number' | 'text';
  min?: number;
  step?: number;
  inline?: boolean;
}) {
  const input = (
    <input
      id={id}
      type={type}
      min={min}
      step={step}
      value={value}
      aria-label={label}
      onChange={(e) => (type === 'number' ? onChange(Number(e.target.value) || 0) : onChange(e.target.value))}
      className={settingsInputCls}
      style={{ fontFamily: FONT_SANS }}
    />
  );
  if (inline) {
    return input;
  }
  return (
    <SettingRow id={id} label={label} hint={hint}>
      {input}
    </SettingRow>
  );
}

export default function SettingsPage() {
  const navigate = useNavigate();
  const { signOut } = useClerk();
  const [settings, setSettings] = useState<Settings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [validationErrors, setValidationErrors] = useState<string[]>([]);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [activeTab, setActiveTab] = useState<TabId>('fund');
  const [userId, setUserId] = useState<string | null>(null);
  const [userIdCopied, setUserIdCopied] = useState(false);

  const isDesktop = useMediaQuery('(min-width: 1024px)');
  const reduceMotion = usePrefersReducedMotion();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const displayName = typeof sessionStorage !== 'undefined' ? sessionStorage.getItem('authUser') : null;
  const handleLogout = () => {
    localStorage.removeItem('aethria_last_activity');
    sessionStorage.removeItem('auth');
    sessionStorage.removeItem('authUser');
    signOut?.().then(() => navigate('/sign-in', { replace: true }));
  };

  const tabs: { id: TabId; label: string }[] = [
    { id: 'fund', label: 'FUND' },
    { id: 'pipeline', label: 'PIPELINE' },
    { id: 'discovery', label: 'DISCOVERY' },
    { id: 'portfolio', label: 'PORTFOLIO' },
    { id: 'budget', label: 'BUDGET' },
    { id: 'account', label: 'ACCOUNT' },
  ];

  const [agentsStatus, setAgentsStatus] = useState<AgentsStatus | null>(null);

  const [thesisSummary, setThesisSummary] = useState<FundThesisSummary | null>(null);
  const [thesisLoading, setThesisLoading] = useState(false);
  const [thesisLoadError, setThesisLoadError] = useState<string | null>(null);
  const [thesisDraft, setThesisDraft] = useState('');
  const [thesisBusy, setThesisBusy] = useState(false);
  const [thesisActivateId, setThesisActivateId] = useState('');
  const [thesisReprocessOpen, setThesisReprocessOpen] = useState(false);
  const [thesisReprocessDryLoading, setThesisReprocessDryLoading] = useState(false);
  const [thesisReprocessEligible, setThesisReprocessEligible] = useState<number | null>(null);
  const [thesisReprocessModalError, setThesisReprocessModalError] = useState<string | null>(null);
  const [thesisReprocessRunning, setThesisReprocessRunning] = useState(false);
  const [thesisReprocessToast, setThesisReprocessToast] = useState<string | null>(null);

  const reloadThesis = () => {
    setThesisLoadError(null);
    setThesisLoading(true);
    fetchFundThesisSummary()
      .then((s) => {
        setThesisSummary(s);
        if (s) {
          setThesisDraft(s.raw_text ?? '');
          const a = s.versions.find((v) => v.is_active);
          setThesisActivateId(a?.id ?? '');
        }
      })
      .catch((e: unknown) => {
        setThesisSummary(null);
        setThesisLoadError(e instanceof Error ? e.message : 'Failed to load thesis');
      })
      .finally(() => setThesisLoading(false));
  };

  useEffect(() => {
    if (activeTab !== 'fund') return;
    if (!agentsStatus?.supabase_configured) return;
    reloadThesis();
  }, [activeTab, agentsStatus?.supabase_configured]);

  useEffect(() => {
    if (!thesisReprocessToast) return;
    const t = window.setTimeout(() => setThesisReprocessToast(null), 6500);
    return () => window.clearTimeout(t);
  }, [thesisReprocessToast]);

  useEffect(() => {
    let cancelled = false;
    fetchMe().then((me) => { if (!cancelled && me) setUserId(me.user_id); });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    let cancelled = false;
    fetchAgentsStatus().then((s) => { if (!cancelled) setAgentsStatus(s ?? null); });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    let cancelled = false;
    setLoadError(null);
    fetchSettings()
      .then((data) => { if (!cancelled) { setSettings(data); setLoadError(null); } })
      .catch((e: unknown) => {
        if (!cancelled) {
          setSettings(null);
          setLoadError(e instanceof Error ? e.message : 'Failed to load settings');
        }
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);

  const handleSave = async () => {
    if (!settings) return;
    setSaving(true);
    setValidationErrors([]);
    setSaveSuccess(false);
    const result = await patchSettings(settings);
    setSaving(false);
    if (result.error) { setValidationErrors(result.error.errors); return; }
    setSaveSuccess(true);
    if (result.data) setSettings(result.data);
  };

  const setCost = <K extends keyof Settings['cost_budget']>(k: K, v: Settings['cost_budget'][K]) =>
    setSettings((s) => s ? { ...s, cost_budget: { ...s.cost_budget, [k]: v } } : s);
  const setAgent = <K extends keyof Settings['agent_config']>(k: K, v: Settings['agent_config'][K]) =>
    setSettings((s) => s ? { ...s, agent_config: { ...s.agent_config, [k]: v } } : s);
  const setPortfolio = <K extends keyof Settings['portfolio']>(k: K, v: Settings['portfolio'][K]) =>
    setSettings((s) => s ? { ...s, portfolio: { ...s.portfolio, [k]: v } } : s);
  const fundIdentity = settings?.fund_identity ?? {
    fund_name: '',
    stage_focus: '',
    geographic_focus: '',
    canonical_website: '',
  };
  const setFundIdentity = <K extends keyof FundIdentity>(k: K, v: string) =>
    setSettings((s) => s ? { ...s, fund_identity: { ...(s.fund_identity ?? fundIdentity), [k]: v } } : s);

  if (loading) {
    return <LoadingAnimation />;
  }
  if (!settings) {
    return (
      <div className="h-screen w-full flex flex-col overflow-hidden bg-paper">
        {!isDesktop && (
          <>
            <MobileHeader onMenuToggle={() => setMobileMenuOpen((o) => !o)} />
            <AnimatePresence>
              {mobileMenuOpen && (
                <motion.section
                  id="mobile-menu"
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: 'auto' }}
                  exit={{ opacity: 0, height: 0 }}
                  transition={transitionOrReduced(reduceMotion, {
                    duration: tokens.motion.duration.micro,
                    ease: tokens.motion.ease,
                  })}
                  className="px-4 pb-0 border-b border-hairline type-label-tab bg-oxford overflow-hidden text-white/70"
                  aria-label="Menu"
                >
                  <div className="flex flex-col items-start gap-3 py-3">
                    <Link to="/v1" className="type-label-section text-white/70 hover:text-white btn-interaction" onClick={() => setMobileMenuOpen(false)}>
                      Overview
                    </Link>
                    <button type="button" onClick={handleLogout} className="type-label-section text-white/50 hover:text-white btn-interaction text-left">
                      Log out
                    </button>
                  </div>
                </motion.section>
              )}
            </AnimatePresence>
          </>
        )}
        <SystemBar navLink={{ href: '/', label: 'Home' }} />
        <main className="flex-1 min-h-0 flex flex-col items-center justify-center gap-3 px-4 pt-4 lg:pl-[calc(9rem+2rem)] lg:pr-6 lg:pt-6">
          <p className="type-label-section text-oxford/60">Failed to load settings.</p>
          {loadError && (
            <p className="type-body-sm text-oxford/80 max-w-md text-center">
              {loadError}
            </p>
          )}
          <p className="type-body-sm text-oxford/60 max-w-md text-center">
            Set VITE_API_URL in the app build to your backend URL. On Render, set ALLOWED_ORIGINS to this app's URL (e.g. https://your-app.vercel.app).
          </p>
        </main>
      </div>
    );
  }

  return (
    <div className="h-screen w-full flex flex-col overflow-hidden bg-paper">
      {!isDesktop && (
        <>
          <MobileHeader onMenuToggle={() => setMobileMenuOpen((open) => !open)} />
          <AnimatePresence>
            {mobileMenuOpen && (
              <motion.section
                id="mobile-menu"
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                transition={transitionOrReduced(reduceMotion, {
                  duration: tokens.motion.duration.micro,
                  ease: tokens.motion.ease,
                })}
                className="px-4 pb-0 border-b border-hairline type-label-tab bg-oxford overflow-hidden text-white/70"
                aria-label="Menu"
              >
                <div className="flex flex-col items-start gap-3 py-3">
                  <div className="flex flex-col items-start gap-1">
                    <Link
                      to="/v1"
                      className="type-label-section text-white/70 hover:text-white btn-interaction"
                      onClick={() => setMobileMenuOpen(false)}
                    >
                      Overview
                    </Link>
                    <span className="type-label-section text-white">Settings</span>
                  </div>
                  <div className="flex flex-col items-start gap-1 mt-3">
                    {displayName && (
                      <span className="type-label-section text-white/60">{displayName}</span>
                    )}
                    <button
                      type="button"
                      onClick={handleLogout}
                      className="type-label-section text-white/50 hover:text-white btn-interaction"
                    >
                      Log out
                    </button>
                  </div>
                </div>
              </motion.section>
            )}
          </AnimatePresence>
        </>
      )}

      <SystemBar agentConfig={settings.agent_config} navLink={{ href: '/', label: 'Home' }} />
      <main className="flex-1 flex flex-col min-h-0 overflow-hidden px-phi-5 pt-phi-5 lg:pl-[calc(9rem+2rem)] lg:pr-phi-6 lg:pt-phi-6 pb-phi-4 lg:pb-phi-5">
        <motion.div
          className="flex-1 flex flex-col min-h-0 overflow-hidden"
          initial={reduceMotion ? { opacity: 1 } : { opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={transitionOrReduced(reduceMotion, {
            duration: tokens.motion.duration.short,
            ease: tokens.motion.ease,
          })}
        >
        <div className="flex-1 min-h-0 flex flex-col overflow-hidden w-full min-w-0 rounded-none border border-hairline bg-paper">
          <PanelShell
            title="SETTINGS"
            titleClassName={SETTINGS_HEADER_LABEL_CLASS}
            headerPaddingClass="py-[10px]"
            headerBorderClass=""
            actions={
              <div className="flex items-center gap-3">
                {saveSuccess && (
                  <p
                    className="m-0 text-[13px] font-normal text-oxford/50"
                    role="status"
                    aria-live="polite"
                    style={{ fontFamily: FONT_SANS }}
                  >
                    Saved
                  </p>
                )}
                <button
                  type="button"
                  onClick={handleSave}
                  disabled={saving}
                  className={SETTINGS_SAVE_BTN_CLASS}
                >
                  {saving ? 'SAVING…' : 'SAVE'}
                </button>
              </div>
            }
            tabs={tabs.map(({ id, label }) => ({ id, label }))}
            activeTab={activeTab}
            onTabChange={(id) => setActiveTab(id as TabId)}
            tabNavClassName={SETTINGS_TAB_NAV_CLASS}
            tabButtonClassName={SETTINGS_TAB_BTN_CLASS}
            tabActiveClassName={SETTINGS_TAB_ACTIVE_CLASS}
            tabInactiveClassName={SETTINGS_TAB_INACTIVE_CLASS}
            contentOverflowHidden
            contentClassName="flex-1 min-h-0 flex flex-col overflow-hidden w-full min-w-0"
          >
            {validationErrors.length > 0 && (
              <div className="flex-none border-b border-oxford/25 bg-warning px-4 py-2 sm:px-5">
                <p className="type-label-section text-oxford/80 mb-1">Validation errors</p>
                <ul className="type-body-sm text-oxford/80 space-y-0.5">
                  {validationErrors.map((e, i) => <li key={i}>{e}</li>)}
                </ul>
              </div>
            )}
            <div className="min-h-0 flex-1 overflow-hidden p-phi-5">
              <div className="h-full flex flex-col gap-8 overflow-hidden">
                <AnimatePresence mode="wait">
                  <motion.div
                    key={activeTab}
                    initial={reduceMotion ? { opacity: 1 } : { opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    transition={transitionOrReduced(reduceMotion, {
                      duration: tokens.motion.duration.short,
                      ease: tokens.motion.ease,
                    })}
                    className="flex flex-col gap-8 min-h-0 overflow-hidden h-full"
                  >

                {/* ——— Fund ——— */}
                {activeTab === 'fund' && (
                  <div className="flex-1 min-h-0 overflow-y-auto flex flex-col gap-10">

                    {/* Fund identity */}
                    <section className="flex flex-col gap-6">
                      <SettingSectionTitle>Fund identity</SettingSectionTitle>
                      <DescText>
                        Your fund name, investment stage, and geography. These appear on the dashboard and help scouts
                        filter out irrelevant companies.
                      </DescText>
                      <div className="flex flex-col gap-6 max-w-sm">
                        <Field
                          id="fund_name"
                          label="Fund name"
                          value={fundIdentity.fund_name}
                          onChange={(v) => setFundIdentity('fund_name', String(v))}
                          type="text"
                        />
                        <Field
                          id="stage_focus"
                          label="Stage focus"
                          hint="e.g. Pre-seed, Seed, Series A"
                          value={fundIdentity.stage_focus}
                          onChange={(v) => setFundIdentity('stage_focus', String(v))}
                          type="text"
                        />
                        <Field
                          id="geographic_focus"
                          label="Geographic focus"
                          hint="e.g. Europe, UK, Global"
                          value={fundIdentity.geographic_focus}
                          onChange={(v) => setFundIdentity('geographic_focus', String(v))}
                          type="text"
                        />
                        <Field
                          id="canonical_website"
                          label="Fund website"
                          hint="Helps scouts filter duplicate or wrong-TLD links from memos"
                          value={fundIdentity.canonical_website ?? ''}
                          onChange={(v) => setFundIdentity('canonical_website', String(v))}
                          type="text"
                        />
                      </div>
                    </section>

                    {/* Divider */}
                    <div className="h-px bg-oxford/[0.07]" aria-hidden />

                    {/* Fund thesis */}
                    <section className="flex flex-col gap-4">
                      <SettingSectionTitle>Investment mandate</SettingSectionTitle>
                      {!agentsStatus?.supabase_configured ? (
                        <DescText>
                          Fund thesis lives in Supabase. Set <code className="type-meta bg-oxford/[0.06] px-1">USE_SUPABASE_STORAGE=1</code> and apply migrations so scouts and reviewers can load your mandate.
                        </DescText>
                      ) : thesisLoading ? (
                        <p className={`m-0 ${settingsDescClass}`} style={{ fontFamily: FONT_SANS }}>Loading thesis…</p>
                      ) : thesisLoadError ? (
                        <p className="m-0 text-[13px] text-red-800/90" style={{ fontFamily: FONT_SANS }}>{thesisLoadError}</p>
                      ) : (
                        <div className="grid grid-cols-1 min-w-0 gap-8 lg:grid-cols-2 lg:gap-x-10 lg:items-start">

                          {/* Active thesis panel */}
                          <div className="flex flex-col gap-4">
                            <DescText>
                              Your active thesis is the mandate given to every scout and reviewer. Publishing a new version takes effect on the next pipeline cycle.
                            </DescText>
                            {thesisSummary ? (
                              <>
                                <p className="m-0 text-[12px] text-oxford/55" style={{ fontFamily: FONT_SANS }}>
                                  Active: version {thesisSummary.active_version_number}
                                  {(thesisSummary.mode ?? 'rule_based') === 'embedding'
                                    ? ' · AI-enhanced'
                                    : ' · Rule-based'}
                                </p>
                                {thesisSummary.embedding?.status === 'pending' && (
                                  <p className="m-0 text-[13px] text-oxford/60 leading-relaxed" style={{ fontFamily: FONT_SANS }}>
                                    Using rule-based scoring. AI-enhanced alignment is available when an OpenAI key is configured.
                                  </p>
                                )}
                                <div
                                  className="min-h-[8rem] max-h-[min(20rem,40vh)] overflow-y-auto border border-oxford/10 p-3 text-[12px] text-oxford/70 whitespace-pre-wrap break-words"
                                  style={{ fontFamily: FONT_SANS }}
                                >
                                  {JSON.stringify(thesisSummary.parsed_json, null, 2)}
                                </div>
                                {thesisSummary.embedding?.status === 'pending' && agentsStatus?.openai_configured ? (
                                  <button
                                    type="button"
                                    disabled={thesisBusy || !(thesisSummary.raw_text || '').trim()}
                                    onClick={() => {
                                      void (async () => {
                                        setThesisBusy(true);
                                        setThesisLoadError(null);
                                        try {
                                          await postFundThesisVersion((thesisSummary.raw_text || '').trim());
                                          reloadThesis();
                                          const s = await fetchAgentsStatus();
                                          setAgentsStatus(s ?? null);
                                        } catch (e) {
                                          setThesisLoadError(e instanceof Error ? e.message : 'Enable embeddings failed');
                                        } finally {
                                          setThesisBusy(false);
                                        }
                                      })();
                                    }}
                                    className="self-start type-meta uppercase tracking-[0.12em] px-4 py-2 border border-oxford/30 text-oxford hover:border-oxford/45 hover:bg-oxford/[0.03] disabled:opacity-40 btn-interaction"
                                  >
                                    {thesisBusy ? 'Working…' : 'Enable AI alignment'}
                                  </button>
                                ) : null}

                                {/* Version history */}
                                {thesisSummary.versions.length > 0 && (
                                  <div className="flex flex-col gap-3 pt-2 border-t border-hairline mt-2">
                                    <span className="type-meta uppercase text-oxford/40">Version history</span>
                                    <div className="flex flex-wrap gap-3 items-center">
                                      <select
                                        value={thesisActivateId}
                                        onChange={(e) => setThesisActivateId(e.target.value)}
                                        className={`${selectCls} min-w-0 flex-1 sm:max-w-xs`}
                                        style={settingsSelectStyle}
                                        aria-label="Select thesis version"
                                      >
                                        {thesisSummary.versions.map((v) => (
                                          <option key={v.id} value={v.id}>
                                            v{v.version_number}{v.is_active ? ' (active)' : ''}
                                          </option>
                                        ))}
                                      </select>
                                      <button
                                        type="button"
                                        disabled={
                                          thesisBusy ||
                                          !thesisActivateId ||
                                          thesisSummary.versions.find((v) => v.id === thesisActivateId)?.is_active
                                        }
                                        onClick={() => {
                                          void (async () => {
                                            setThesisBusy(true);
                                            setThesisLoadError(null);
                                            try {
                                              await patchFundThesisActiveVersion(thesisActivateId);
                                              reloadThesis();
                                              const s = await fetchAgentsStatus();
                                              setAgentsStatus(s ?? null);
                                            } catch (e) {
                                              setThesisLoadError(e instanceof Error ? e.message : 'Activate failed');
                                            } finally {
                                              setThesisBusy(false);
                                            }
                                          })();
                                        }}
                                        className="type-meta uppercase tracking-[0.12em] px-3 py-2 border border-oxford/30 text-oxford hover:border-oxford/45 hover:bg-oxford/[0.03] btn-interaction disabled:opacity-40"
                                      >
                                        Set active
                                      </button>
                                    </div>
                                  </div>
                                )}

                                {/* Reprocess */}
                                <div className="flex flex-col gap-3 pt-2 border-t border-hairline mt-2">
                                  <span className="type-meta uppercase text-oxford/40">Apply to existing pipeline</span>
                                  <DescText>Re-run your mandate against previously reviewed startups.</DescText>
                                  {thesisReprocessToast && (
                                    <p className="m-0 text-[13px] text-oxford/70" role="status" aria-live="polite" style={{ fontFamily: FONT_SANS }}>
                                      {thesisReprocessToast}
                                    </p>
                                  )}
                                  <button
                                    type="button"
                                    disabled={thesisBusy || thesisReprocessRunning}
                                    onClick={() => {
                                      setThesisReprocessOpen(true);
                                      setThesisReprocessModalError(null);
                                      setThesisReprocessEligible(null);
                                      setThesisReprocessDryLoading(true);
                                      void postFundThesisReprocessMissing({ dryRun: true })
                                        .then((r) => {
                                          if ('eligible' in r) setThesisReprocessEligible(r.eligible);
                                        })
                                        .catch((e: unknown) => {
                                          setThesisReprocessModalError(e instanceof Error ? e.message : 'Could not load count');
                                        })
                                        .finally(() => setThesisReprocessDryLoading(false));
                                    }}
                                    className="self-start type-meta uppercase tracking-[0.12em] px-4 py-2 border border-oxford/30 text-oxford hover:border-oxford/45 hover:bg-oxford/[0.03] disabled:opacity-40 btn-interaction"
                                  >
                                    Reprocess startups
                                  </button>
                                </div>
                              </>
                            ) : (
                              <DescText>No mandate yet. Paste your investment thesis in the editor and publish.</DescText>
                            )}
                          </div>

                          {/* Publish editor */}
                          <div className="flex flex-col gap-4 border-t border-hairline pt-8 lg:border-t-0 lg:border-l lg:pt-0 lg:pl-10">
                            <DescText>
                              Write your mandate in plain English: sectors, stage, geography, check size, exclusions, and any hard filters. The pipeline parses this automatically.
                            </DescText>
                            <textarea
                              value={thesisDraft}
                              onChange={(e) => setThesisDraft(e.target.value)}
                              rows={12}
                              className="min-h-[12rem] w-full min-w-0 resize-y border border-oxford/15 bg-paper p-3 text-[13px] text-oxford/85 outline-none focus:border-oxford/40"
                              style={{ fontFamily: FONT_SANS }}
                              placeholder="Fund mandate: sectors, stage, geography, exclusions, check size, risk posture…"
                            />
                            <button
                              type="button"
                              disabled={thesisBusy || !thesisDraft.trim()}
                              onClick={() => {
                                void (async () => {
                                  setThesisBusy(true);
                                  setThesisLoadError(null);
                                  try {
                                    await postFundThesisVersion(thesisDraft.trim());
                                    reloadThesis();
                                    const s = await fetchAgentsStatus();
                                    setAgentsStatus(s ?? null);
                                  } catch (e) {
                                    setThesisLoadError(e instanceof Error ? e.message : 'Publish failed');
                                  } finally {
                                    setThesisBusy(false);
                                  }
                                })();
                              }}
                              className="self-start type-meta uppercase tracking-[0.12em] px-4 py-2 border border-oxford/30 text-oxford hover:border-oxford/45 hover:bg-oxford/[0.03] disabled:opacity-40 btn-interaction"
                            >
                              {thesisBusy ? 'Publishing…' : 'Publish new version'}
                            </button>
                          </div>
                        </div>
                      )}
                    </section>
                  </div>
                )}

                {/* ——— Pipeline ——— */}
                {activeTab === 'pipeline' && (
                  <div className="flex flex-col gap-8 min-h-0 overflow-y-auto">
                    {agentsStatus && !agentsStatus.agents_will_run && (
                      <div className="border border-oxford/12 bg-oxford/[0.03] px-4 py-3">
                        <p className="type-label-section text-oxford/70 mb-1">Pipeline may not be running</p>
                        <p className="m-0 text-[12px] text-oxford/50" style={{ fontFamily: FONT_SANS }}>
                          Worker: {agentsStatus.worker_ready ? 'ready' : 'not ready'} · Supabase: {agentsStatus.supabase_configured ? 'ok' : 'missing'} · OpenAI: {agentsStatus.openai_configured ? 'ok' : 'missing'}
                        </p>
                      </div>
                    )}

                    <section className="flex flex-col gap-6">
                      <SettingSectionTitle>Pipeline stages</SettingSectionTitle>
                      <DescText>
                        Enable or pause each stage of the deal-flow pipeline. Scouts discover companies, Reviewers score them against your mandate, Partners make the final call.
                      </DescText>
                      <div className="flex flex-col gap-6">
                        <Toggle
                          id="scouts_enabled"
                          checked={settings.agent_config.scouts_enabled}
                          onChange={(v) => setAgent('scouts_enabled', v)}
                          label="Scouts"
                          hint="AI agents that discover new companies matching your mandate"
                        />
                        <Toggle
                          id="reviewers_enabled"
                          checked={settings.agent_config.reviewers_enabled}
                          onChange={(v) => setAgent('reviewers_enabled', v)}
                          label="Reviewers"
                          hint="Score companies across market, product, team, and defensibility"
                        />
                        <Toggle
                          id="partners_enabled"
                          checked={settings.agent_config.partners_enabled}
                          onChange={(v) => setAgent('partners_enabled', v)}
                          label="Partners"
                          hint="Automated decision engine — YES / MAYBE / NO with written rationale"
                        />
                      </div>
                    </section>

                    <section className="flex flex-col gap-6">
                      <SettingSectionTitle>Run settings</SettingSectionTitle>
                      <DescText>Controls how many companies are evaluated each cycle and how confident the pipeline must be before making an automated call.</DescText>
                      <div className="flex flex-col gap-6">
                        <Field
                          id="max_agents"
                          label="Companies per cycle"
                          hint="How many new companies to source and evaluate each pipeline run"
                          value={settings.agent_config.max_agents_per_run}
                          onChange={(v) => setAgent('max_agents_per_run', Number(v))}
                          min={1}
                        />
                        <SettingRow id="confidence_threshold" label="Decision threshold" hint="Minimum confidence score to make an automated pass/invest call (0–1). Lower = more decisions, higher = more human review.">
                          <input
                            id="confidence_threshold"
                            type="text"
                            value={typeof settings.agent_config.confidence_threshold === 'number' ? String(settings.agent_config.confidence_threshold) : settings.agent_config.confidence_threshold}
                            onChange={(e) => {
                              const v = e.target.value;
                              const n = Number(v);
                              setAgent('confidence_threshold', v.trim() === '' ? 0.5 : Number.isFinite(n) ? n : v);
                            }}
                            className={settingsInputCls}
                            style={{ fontFamily: FONT_SANS }}
                            aria-label="Decision threshold 0 to 1"
                          />
                        </SettingRow>
                      </div>
                    </section>

                    {settings.meta_agent && (
                      <section className="flex flex-col gap-6">
                        <SettingSectionTitle>Self-optimisation</SettingSectionTitle>
                        <DescText>
                          The optimisation agent analyses past decisions and automatically reweights scouts and adjusts thresholds. Runs on a cadence you define.
                        </DescText>
                        <div className="flex flex-col gap-6">
                          <Toggle
                            id="meta_enabled"
                            checked={settings.meta_agent.enabled}
                            onChange={(v) => setSettings((s) => s ? { ...s, meta_agent: { ...(s.meta_agent ?? settings.meta_agent!), enabled: v } } : s)}
                            label="Enable self-optimisation"
                          />
                          <Field
                            id="meta_interval"
                            label="Optimisation interval (seconds)"
                            hint="How often the optimisation agent runs (86400 = daily)"
                            value={settings.meta_agent.interval_seconds}
                            onChange={(v) => setSettings((s) => s ? { ...s, meta_agent: { ...(s.meta_agent ?? settings.meta_agent!), interval_seconds: Number(v) } } : s)}
                            min={0}
                          />
                          <Field
                            id="meta_min_reviews"
                            label="Minimum reviews before optimising"
                            hint="Won't tune until this many startups have been scored"
                            value={settings.meta_agent.min_reviews}
                            onChange={(v) => setSettings((s) => s ? { ...s, meta_agent: { ...(s.meta_agent ?? settings.meta_agent!), min_reviews: Number(v) } } : s)}
                            min={0}
                          />
                          <Field
                            id="meta_min_decisions"
                            label="Minimum decisions before optimising"
                            hint="Won't tune until this many partner decisions have been logged"
                            value={settings.meta_agent.min_decisions}
                            onChange={(v) => setSettings((s) => s ? { ...s, meta_agent: { ...(s.meta_agent ?? settings.meta_agent!), min_decisions: Number(v) } } : s)}
                            min={0}
                          />
                          <Field
                            id="meta_cooldown"
                            label="Cooldown (cycles)"
                            hint="How many cycles to wait before allowing another optimisation pass"
                            value={settings.meta_agent.mutation_cooldown_cycles}
                            onChange={(v) => setSettings((s) => s ? { ...s, meta_agent: { ...(s.meta_agent ?? settings.meta_agent!), mutation_cooldown_cycles: Number(v) } } : s)}
                            min={0}
                          />
                        </div>
                      </section>
                    )}
                  </div>
                )}

                {/* ——— Discovery ——— */}
                {activeTab === 'discovery' && (
                  <div className="flex flex-col gap-8 min-h-0">
                    <section className="flex flex-col gap-6">
                      <SettingSectionTitle>Search scope</SettingSectionTitle>
                      <DescText>Where scouts look for companies. Narrowing the region keeps results relevant to your mandate and reduces noise.</DescText>
                      <div className="flex flex-col gap-6">
                        <SettingRow id="scout_region" label="Target region">
                          <select
                            id="scout_region"
                            value={settings.agent_config.scout_region}
                            onChange={(e) => setAgent('scout_region', e.target.value)}
                            className={selectCls}
                            style={settingsSelectStyle}
                          >
                            <option value="europe">Europe</option>
                            <option value="global">Global</option>
                          </select>
                        </SettingRow>
                        <Toggle
                          id="scout_serp_enabled"
                          checked={settings.agent_config.scout_serp_enabled}
                          onChange={(v) => setAgent('scout_serp_enabled', v)}
                          label="Enable web search"
                          hint="Scouts use live web searches to surface recently founded companies and news signals"
                        />
                        <Field
                          id="scout_serp_budget"
                          label="Daily web searches"
                          hint="Maximum number of search queries scouts can make per day"
                          value={settings.agent_config.scout_serp_daily_budget}
                          onChange={(v) => setAgent('scout_serp_daily_budget', Number(v))}
                          min={0}
                        />
                      </div>
                    </section>
                  </div>
                )}

                {/* ——— Portfolio ——— */}
                {activeTab === 'portfolio' && (
                  <div className="flex flex-col gap-8 min-h-0">
                    <section className="flex flex-col gap-6">
                      <SettingSectionTitle>Watchlist</SettingSectionTitle>
                      <DescText>Companies marked as strong signals are automatically added to your watchlist for ongoing monitoring.</DescText>
                      <Toggle
                        id="auto_watchlist"
                        checked={settings.portfolio.auto_watchlist}
                        onChange={(v) => setPortfolio('auto_watchlist', v)}
                        label="Auto-add high-signal companies"
                        hint="When enabled, companies scoring above the signal threshold are added automatically"
                      />
                    </section>
                    <section className="flex flex-col gap-6">
                      <SettingSectionTitle>Monitoring</SettingSectionTitle>
                      <DescText>How often Aethria checks for new signals on watchlisted companies and how detailed the resulting memos are.</DescText>
                      <div className="flex flex-col gap-6">
                        <SettingRow id="signal_scan" label="Signal scan frequency">
                          <select
                            id="signal_scan"
                            value={settings.portfolio.signal_scan_frequency}
                            onChange={(e) => setPortfolio('signal_scan_frequency', e.target.value)}
                            className={selectCls}
                            style={settingsSelectStyle}
                          >
                            <option value="hourly">Hourly</option>
                            <option value="every_6h">Every 6 hours</option>
                            <option value="daily">Daily</option>
                          </select>
                        </SettingRow>
                        <SettingRow id="memo_verbosity" label="Memo depth">
                          <select
                            id="memo_verbosity"
                            value={settings.portfolio.memo_verbosity}
                            onChange={(e) => setPortfolio('memo_verbosity', e.target.value)}
                            className={selectCls}
                            style={settingsSelectStyle}
                          >
                            <option value="minimal">Brief</option>
                            <option value="standard">Standard</option>
                            <option value="full">Full</option>
                          </select>
                        </SettingRow>
                      </div>
                    </section>
                  </div>
                )}

                {/* ——— Budget ——— */}
                {activeTab === 'budget' && (
                  <div className="flex flex-col gap-8 min-h-0 overflow-y-auto">
                    <section className="flex flex-col gap-6">
                      <SettingSectionTitle>Spending controls</SettingSectionTitle>
                      <DescText>Set daily and weekly ceilings on AI spend. The pipeline pauses automatically when a cap is hit and resumes after the cooldown.</DescText>
                      <Toggle
                        id="cost_budget_enabled"
                        checked={settings.cost_budget?.enabled ?? false}
                        onChange={(v) => setCost('enabled', v)}
                        label="Enable spending limits"
                      />
                    </section>
                    <section className="flex flex-col gap-6">
                      <SettingSectionTitle>Caps</SettingSectionTitle>
                      <div className="flex flex-col gap-6">
                        <Field
                          id="daily_ceiling"
                          label="Daily cap (USD)"
                          value={settings.cost_budget.daily_cost_ceiling}
                          onChange={(v) => setCost('daily_cost_ceiling', Number(v))}
                          min={0}
                          step={0.01}
                        />
                        <Field
                          id="weekly_ceiling"
                          label="Weekly cap (USD)"
                          value={settings.cost_budget.weekly_cost_ceiling}
                          onChange={(v) => setCost('weekly_cost_ceiling', Number(v))}
                          min={0}
                          step={0.01}
                        />
                        <Field
                          id="max_tokens"
                          label="Token budget per cycle"
                          hint="Max AI tokens consumed in a single pipeline run"
                          value={settings.cost_budget.max_tokens_per_run}
                          onChange={(v) => setCost('max_tokens_per_run', Number(v))}
                          min={0}
                        />
                        <Field
                          id="cooldown"
                          label="Rate-limit cooldown (seconds)"
                          hint="How long the pipeline pauses after hitting a cap before retrying"
                          value={settings.cost_budget.cooldown_seconds}
                          onChange={(v) => setCost('cooldown_seconds', Number(v))}
                          min={0}
                        />
                      </div>
                    </section>
                    {settings.system_health && settings.system_health.budget_status.length > 0 ? (
                      <section className="flex flex-col gap-6">
                        <SettingSectionTitle>Usage today</SettingSectionTitle>
                        <div className="flex flex-col gap-2 max-w-md">
                          {settings.system_health.budget_status.map((b: AgentBudgetStatus) => {
                            const callsPct = b.daily_calls_limit > 0 ? (b.daily_calls_used / b.daily_calls_limit) : 0;
                            const tokensPct = b.daily_tokens_limit > 0 ? (b.daily_tokens_used / b.daily_tokens_limit) : 0;
                            const callsWidth = `${Math.min(100, callsPct * 100)}%`;
                            const tokensWidth = `${Math.min(100, tokensPct * 100)}%`;
                            return (
                              <div key={b.agent_id} className="border border-hairline p-2 space-y-1">
                                <p className="type-label-section text-oxford/80 truncate">{b.agent_id}</p>
                                <div>
                                  <p className="type-meta text-oxford/60">Calls {b.daily_calls_used}/{b.daily_calls_limit}</p>
                                  <div className="w-full h-1 bg-oxford/25"><div className="h-full bg-oxford/40" style={{ width: callsWidth }} /></div>
                                </div>
                                <div>
                                  <p className="type-meta text-oxford/60">Tokens {b.daily_tokens_used}/{b.daily_tokens_limit}</p>
                                  <div className="w-full h-1 bg-oxford/25"><div className="h-full bg-oxford/40" style={{ width: tokensWidth }} /></div>
                                </div>
                                {b.in_cooldown && <p className="type-meta text-oxford/60">Cooldown until {b.cooldown_until ?? '—'}</p>}
                              </div>
                            );
                          })}
                        </div>
                      </section>
                    ) : (
                      <section className="flex flex-col gap-6">
                        <SettingSectionTitle>Usage today</SettingSectionTitle>
                        <p className="m-0 text-[13px] font-normal text-oxford/[0.35] italic leading-relaxed max-w-xl" style={{ fontFamily: FONT_SANS }}>
                          No usage recorded yet.
                        </p>
                      </section>
                    )}
                  </div>
                )}

                {/* ——— Account ——— */}
                {activeTab === 'account' && (
                  <div className="flex-1 min-h-0 overflow-y-auto flex flex-col gap-8">
                    <section className="flex flex-col gap-6">
                      <SettingSectionTitle>Profile & security</SettingSectionTitle>
                      <DescText>Change your email, password, or manage active sessions.</DescText>
                      <div className="aethria-clerk-profile min-h-[320px] border border-hairline bg-paper">
                        <UserProfile
                          appearance={userProfileAppearance}
                          routing="hash"
                        />
                      </div>
                    </section>
                    {userId && (
                      <section className="flex flex-col gap-4">
                        <SettingSectionTitle>User ID</SettingSectionTitle>
                        <DescText>
                          Your Clerk user ID. If you self-host the backend and run agents locally, set{' '}
                          <code className="type-meta bg-oxford/[0.06] px-1">AETHRIA_AGENT_USER_ID</code> to this value in your backend <code className="type-meta bg-oxford/[0.06] px-1">.env</code>.
                        </DescText>
                        <div className="flex items-center gap-2 flex-wrap">
                          <code className="type-meta text-oxford/80 bg-oxford/[0.06] px-2 py-1 select-none" aria-hidden="true">
                            {userId.replace(/./g, '•')}
                          </code>
                          <button
                            type="button"
                            onClick={() => navigator.clipboard?.writeText(userId).then(() => { setUserIdCopied(true); setTimeout(() => setUserIdCopied(false), 2000); })}
                            className="border border-solid border-oxford/20 bg-transparent py-[3px] px-2 text-[13px] font-normal text-oxford/[0.75] hover:text-oxford hover:border-oxford/40 hover:bg-oxford/[0.03] transition-colors duration-150 btn-interaction focus:outline-none focus-visible:ring-2 focus-visible:ring-oxford/40 focus-visible:ring-inset"
                            style={{ fontFamily: FONT_SANS }}
                          >
                            {userIdCopied ? 'Copied' : 'Copy'}
                          </button>
                        </div>
                      </section>
                    )}
                  </div>
                )}

                  </motion.div>
                </AnimatePresence>
              </div>
            </div>
          </PanelShell>
        </div>
        </motion.div>
      </main>

      {thesisReprocessOpen ? (
        <div
          className="fixed inset-0 z-[220] flex items-center justify-center bg-oxford/40 px-4"
          role="presentation"
          onClick={() => {
            if (!thesisReprocessRunning) setThesisReprocessOpen(false);
          }}
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="thesis-reprocess-title"
            className="max-w-md w-full border border-oxford/15 bg-paper p-5 shadow-lg"
            onClick={(e) => e.stopPropagation()}
            style={{ fontFamily: FONT_SANS }}
          >
            <h2 id="thesis-reprocess-title" className="type-label-section text-oxford m-0 mb-3">
              Reprocess startups?
            </h2>
            <p className="m-0 text-[13px] text-oxford/70 leading-relaxed mb-4">
              This will re-run analysis on existing startups that were evaluated before your current mandate was active. May take a few minutes.
            </p>
            {thesisReprocessDryLoading ? (
              <p className="m-0 text-[12px] text-oxford/50 mb-2">Counting eligible startups…</p>
            ) : thesisReprocessModalError ? (
              <p className="m-0 text-[12px] text-red-800/90 mb-2">{thesisReprocessModalError}</p>
            ) : thesisReprocessEligible !== null ? (
              <>
                <p className="m-0 text-[12px] text-oxford/60 mb-2">
                  {thesisReprocessEligible} startup{thesisReprocessEligible === 1 ? '' : 's'} will be updated.
                </p>
                {thesisReprocessEligible > 500 ? (
                  <p className="m-0 text-[12px] text-amber-900/90 mb-3">
                    Large batch: only the first 1000 are processed per run. Run again if needed.
                  </p>
                ) : null}
                {!agentsStatus?.openai_configured && thesisReprocessEligible !== null && thesisReprocessEligible >= 1 ? (
                  <p className="m-0 text-[12px] text-oxford/45 mb-3">
                    Configure <code className="type-meta bg-oxford/[0.06] px-1">OPENAI_API_KEY</code> on the server to continue.
                  </p>
                ) : null}
              </>
            ) : null}
            <div className="flex flex-wrap gap-2 justify-end">
              <button
                type="button"
                disabled={thesisReprocessRunning}
                className="type-meta uppercase tracking-[0.12em] px-3 py-2 border border-oxford/20 text-oxford/70 hover:text-oxford hover:border-oxford/40 hover:bg-oxford/[0.03] btn-interaction disabled:opacity-40"
                onClick={() => setThesisReprocessOpen(false)}
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={
                  thesisReprocessRunning ||
                  thesisReprocessDryLoading ||
                  thesisReprocessEligible === null ||
                  thesisReprocessEligible < 1 ||
                  !!thesisReprocessModalError ||
                  !agentsStatus?.openai_configured
                }
                className="type-meta uppercase tracking-[0.12em] px-3 py-2 border border-oxford/30 text-oxford hover:border-oxford/45 hover:bg-oxford/[0.03] btn-interaction disabled:opacity-40 inline-flex items-center gap-2"
                onClick={() => {
                  void (async () => {
                    setThesisReprocessRunning(true);
                    setThesisReprocessModalError(null);
                    try {
                      const r = await postFundThesisReprocessMissing();
                      if (!('processed' in r)) return;
                      setThesisReprocessOpen(false);
                      let msg = `Reprocessed ${r.processed} startup${r.processed === 1 ? '' : 's'}`;
                      if (r.failed > 0) msg += ` (${r.failed} failed)`;
                      setThesisReprocessToast(msg);
                    } catch (e: unknown) {
                      setThesisReprocessModalError(e instanceof Error ? e.message : 'Reprocess failed');
                    } finally {
                      setThesisReprocessRunning(false);
                    }
                  })();
                }}
              >
                {thesisReprocessRunning ? (
                  <>
                    <svg className="animate-spin h-4 w-4 text-oxford" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" aria-hidden>
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                    </svg>
                    <span>Reprocessing…</span>
                  </>
                ) : (
                  'Continue'
                )}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
