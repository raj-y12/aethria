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
import { tokens } from '../design-system/tokens';
import { userProfileAppearance } from '../design-system/clerk-appearance';
import { transitionOrReduced } from '../design-system/motion';
import { useMediaQuery, usePrefersReducedMotion } from '../hooks';

type TabId = 'account' | 'budget' | 'pipeline' | 'discovery' | 'meta' | 'portfolio';

const FONT_GEIST = '"Geist Sans", system-ui, sans-serif' as const;

const SETTINGS_HEADER_LABEL_CLASS =
  'type-meta uppercase text-oxford/40';

const SETTINGS_SAVE_BTN_CLASS =
  `${SETTINGS_HEADER_LABEL_CLASS} rounded-none border-0 bg-transparent p-0 cursor-pointer hover:text-oxford/80 transition-colors duration-150 ease-out btn-interaction focus:outline-none focus-visible:ring-2 focus-visible:ring-oxford/40 focus-visible:ring-inset`;

const SETTINGS_TAB_NAV_CLASS = `${PANEL_TAB_BAR_CLASS} pt-2 pb-0`;
const SETTINGS_TAB_BTN_CLASS =
  'py-2.5 px-3 type-label-tab border-b border-transparent -mb-px focus:outline-none focus-visible:ring-2 focus-visible:ring-oxford/40 focus-visible:ring-inset btn-interaction';
const SETTINGS_TAB_ACTIVE_CLASS = 'border-b border-oxford text-oxford/[0.9]';
const SETTINGS_TAB_INACTIVE_CLASS =
  'border-b border-transparent text-oxford/[0.35] hover:border-oxford/15 hover:text-oxford/55';

/** Geist 13px / 50% — section descriptions */
const settingsDescClass =
  'max-w-xl leading-relaxed m-0 text-[13px] font-normal text-oxford/50';

/** Geist 13px / 75% — field labels */
const settingsFieldLabelClass = 'text-[13px] font-normal text-oxford/[0.75]';

const settingsInputCls =
  'w-full min-w-0 max-w-[10rem] appearance-none bg-transparent border-0 border-b border-solid border-oxford/20 rounded-none shadow-none outline-none ring-0 focus:ring-0 focus:border-oxford/60 focus:outline-none transition-[border-color] duration-150 ease-out text-[14px] font-normal text-oxford/[0.85] py-[6px] px-0 placeholder:text-oxford/35 btn-interaction [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none [-moz-appearance:textfield]';

const SELECT_CHEVRON =
  "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='10' viewBox='0 0 10 10'%3E%3Cpath fill='%23002147' fill-opacity='0.5' d='M0 3h10L5 8z'/%3E%3C/svg%3E\")";

const selectCls =
  `${settingsInputCls} cursor-pointer max-w-full pr-8 bg-no-repeat bg-[length:10px] bg-[center_right_2px]`;

const settingsSelectStyle: CSSProperties = {
  fontFamily: FONT_GEIST,
  backgroundImage: SELECT_CHEVRON,
};

const hintCls = `block mt-1 mb-0 ${settingsDescClass}`;

/** Slight radius — institutional, not pill-shaped. */
const TOGGLE_TRACK =
  'h-6 w-11 shrink-0 cursor-pointer inline-flex items-center overflow-hidden rounded-[3px]';
const TOGGLE_KNOB = 'h-4 w-4 rounded-[2px] pointer-events-none block';

function SettingSectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <div>
      <div className="type-meta uppercase text-oxford/50 mb-2">
        {children}
      </div>
      <div className="h-px w-full bg-oxford/10 mb-5" aria-hidden />
    </div>
  );
}

function DescText({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return (
    <p className={`${settingsDescClass} ${className}`} style={{ fontFamily: FONT_GEIST }}>
      {children}
    </p>
  );
}

/** Single setting row: label (and hint) left, control right. Use for consistent alignment across tabs. */
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
          <label htmlFor={id} className={settingsFieldLabelClass} style={{ fontFamily: FONT_GEIST }}>
            {label}
          </label>
        ) : (
          <span className={settingsFieldLabelClass} style={{ fontFamily: FONT_GEIST }}>
            {label}
          </span>
        )}
        {hint && (
          <div className={hintCls} style={{ fontFamily: FONT_GEIST }}>
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
  /** When true, render only the input (for use inside SettingRow). */
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
      style={{ fontFamily: FONT_GEIST }}
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
  const [activeTab, setActiveTab] = useState<TabId>('budget');
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

  const tabs: { id: TabId; label: string }[] = (
    [
      { id: 'budget', label: 'BUDGET' },
      { id: 'pipeline', label: 'PIPELINE' },
      { id: 'discovery', label: 'DISCOVERY' },
      { id: 'meta', label: 'META-AGENT' },
      { id: 'portfolio', label: 'PORTFOLIO' },
      { id: 'account', label: 'ACCOUNT' },
    ] as { id: TabId; label: string }[]
  ).filter((t) => t.id !== 'meta' || (settings?.meta_agent != null));

  const [agentsStatus, setAgentsStatus] = useState<AgentsStatus | null>(null);

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

  // When Meta-agent tab is hidden (no meta_agent), switch away from it
  useEffect(() => {
    if (settings && activeTab === 'meta' && settings.meta_agent == null) {
      setActiveTab('budget');
    }
  }, [settings, activeTab]);

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
        <SystemBar scoutCount={0} navLink={{ href: '/', label: 'Home' }} />
        <main className="flex-1 min-h-0 flex flex-col items-center justify-center gap-3 px-4 pt-4 lg:pl-[11rem] lg:pr-6 lg:pt-6">
          <p className="type-label-section text-oxford/60">Failed to load settings.</p>
          {loadError && (
            <p className="type-body-sm text-oxford/80 max-w-md text-center">
              {loadError}
            </p>
          )}
          <p className="type-body-sm text-oxford/60 max-w-md text-center">
            Set VITE_API_URL in the app build to your backend URL. On Render, set ALLOWED_ORIGINS to this app’s URL (e.g. https://your-app.vercel.app).
          </p>
        </main>
      </div>
    );
  }

  return (
    <div className="h-screen w-full flex flex-col overflow-hidden bg-paper">
      {/* Mobile / tablet top nav — desktop keeps the vertical SystemBar only */}
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
                  {/* Nav links */}
                  <div className="flex flex-col items-start gap-1">
                    <Link
                      to="/v1"
                      className="type-label-section text-white/70 hover:text-white btn-interaction"
                      onClick={() => setMobileMenuOpen(false)}
                    >
                      Overview
                    </Link>
                    <span className="type-label-section text-white">
                      Settings
                    </span>
                  </div>

                  {/* Username / logout */}
                  <div className="flex flex-col items-start gap-1 mt-3">
                    {displayName && (
                      <span
                        className="type-label-section text-white/60"
                      >
                        {displayName}
                      </span>
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

      <SystemBar scoutCount={0} agentConfig={settings.agent_config} navLink={{ href: '/', label: 'Home' }} />
      {/* Main: fixed height so only the content inside the bordered grid scrolls (same as WorkGrid). */}
      <main className="flex-1 flex flex-col min-h-0 overflow-hidden px-4 pt-4 lg:pl-[11rem] lg:pr-6 lg:pt-6 pb-3 lg:pb-4">
        <motion.div
          className="flex-1 flex flex-col min-h-0 overflow-hidden"
          initial={reduceMotion ? { opacity: 1 } : { opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={transitionOrReduced(reduceMotion, {
            duration: tokens.motion.duration.short,
            ease: tokens.motion.ease,
          })}
        >
        <header className="mb-2 hidden min-w-0 flex-none lg:block">
          <h1 className="font-display font-normal text-[20px] leading-[1.4] text-oxford">
            Aethria
          </h1>
          {fundIdentity.fund_name?.trim() && (
            <p className="type-meta mt-1 tracking-[0.12em] text-oxford/50" aria-hidden>
              {[
                fundIdentity.fund_name.trim(),
                fundIdentity.stage_focus?.trim(),
                fundIdentity.geographic_focus?.trim(),
              ]
                .filter(Boolean)
                .join(' · ')}
            </p>
          )}
        </header>
        {/* Bordered grid: static border; only inner content scrolls (WorkGrid pattern). */}
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
                    style={{ fontFamily: FONT_GEIST }}
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
            <div className="min-h-0 flex-1 overflow-hidden p-4 sm:p-5">
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
                {/* ——— Account ——— */}
                {activeTab === 'account' && (
                  <div className="flex-1 min-h-0 overflow-y-auto flex flex-col gap-8">
                    {agentsStatus && !agentsStatus.agents_will_run && (
                      <section className="flex flex-col gap-6">
                        <SettingSectionTitle>Agents may not run on this server</SettingSectionTitle>
                        <DescText>
                          Set <code className="type-meta bg-oxford/[0.06] px-1 rounded">USE_SUPABASE_STORAGE=1</code>, <code className="type-meta bg-oxford/[0.06] px-1 rounded">OPENAI_API_KEY</code>, <code className="type-meta bg-oxford/[0.06] px-1 rounded">SUPABASE_URL</code>, <code className="type-meta bg-oxford/[0.06] px-1 rounded">SUPABASE_SERVICE_ROLE_KEY</code> in your host environment. See AGENTS.md.
                        </DescText>
                        <p className="type-meta text-oxford/60 m-0">
                          Worker: {agentsStatus.worker_ready ? 'ready' : 'not ready'} · Supabase: {agentsStatus.supabase_configured ? 'ok' : 'missing'} · OpenAI: {agentsStatus.openai_configured ? 'ok' : 'missing'}
                        </p>
                      </section>
                    )}
                    <section className="flex flex-col gap-6">
                      <SettingSectionTitle>Fund identity</SettingSectionTitle>
                      <DescText>
                        Shown on the dashboard (desktop). Fund name, stage focus, and geographic focus. Set your real
                        website so Scouts drop parallel wrong-TLD links (e.g. .com vs your .co) from memo sources.
                      </DescText>
                      <div className="flex flex-col gap-6">
                        <Field id="fund_name" label="Fund name" value={fundIdentity.fund_name} onChange={(v) => setFundIdentity('fund_name', String(v))} type="text" />
                        <Field id="stage_focus" label="Stage focus" value={fundIdentity.stage_focus} onChange={(v) => setFundIdentity('stage_focus', String(v))} type="text" />
                        <Field id="geographic_focus" label="Geographic focus" value={fundIdentity.geographic_focus} onChange={(v) => setFundIdentity('geographic_focus', String(v))} type="text" />
                        <Field
                          id="canonical_website"
                          label="Canonical website (optional)"
                          value={fundIdentity.canonical_website ?? ''}
                          onChange={(v) => setFundIdentity('canonical_website', String(v))}
                          type="text"
                        />
                      </div>
                    </section>
                    {userId && (
                      <section className="flex flex-col gap-6">
                        <SettingSectionTitle>Your user ID</SettingSectionTitle>
                        <DescText>
                          Clerk user ID; used for startups, settings, and agents. For <code className="type-meta bg-oxford/[0.06] px-1 rounded">run.py</code> agents, set <code className="type-meta bg-oxford/[0.06] px-1 rounded">AETHRIA_AGENT_USER_ID</code> to this in backend .env.
                        </DescText>
                        <div className="flex items-center gap-2 flex-wrap">
                          <code className="type-meta text-oxford/80 bg-oxford/[0.06] px-2 py-1 rounded select-none" aria-hidden="true">
                            {userId.replace(/./g, '•')}
                          </code>
                          <button
                            type="button"
                            onClick={() => navigator.clipboard?.writeText(userId).then(() => { setUserIdCopied(true); setTimeout(() => setUserIdCopied(false), 2000); })}
                            className="rounded-none border border-solid border-oxford/20 bg-transparent py-[3px] px-2 text-[13px] font-normal text-oxford/[0.75] hover:text-oxford transition-colors duration-150 btn-interaction focus:outline-none focus-visible:ring-2 focus-visible:ring-oxford/40 focus-visible:ring-inset"
                            style={{ fontFamily: FONT_GEIST }}
                          >
                            {userIdCopied ? 'Copied' : 'Copy'}
                          </button>
                        </div>
                      </section>
                    )}
                    <section className="flex flex-col gap-6">
                      <SettingSectionTitle>Account & security</SettingSectionTitle>
                      <DescText>
                        Change password, update email, or manage security and sessions.
                      </DescText>
                      <div className="aethria-clerk-profile min-h-[320px] border border-hairline bg-paper">
                        <UserProfile
                          appearance={userProfileAppearance}
                          routing="hash"
                        />
                      </div>
                    </section>
                  </div>
                )}

                {/* ——— Budget ——— */}
                {activeTab === 'budget' && (
                  <div className="flex flex-col gap-8 min-h-0">
                    <section className="flex flex-col gap-6">
                      <SettingSectionTitle>Budget</SettingSectionTitle>
                      <DescText>Enable to enforce token and cost limits.</DescText>
                      <Toggle id="cost_budget_enabled" checked={settings.cost_budget?.enabled ?? false} onChange={(v) => setCost('enabled', v)} label="Enable cost budget" />
                    </section>
                    <section className="flex flex-col gap-6">
                      <SettingSectionTitle>Limits</SettingSectionTitle>
                      <DescText>Caps and cooldown after a limit is hit.</DescText>
                      <div className="flex flex-col gap-6">
                        <Field id="max_tokens" label="Tokens per run" value={settings.cost_budget.max_tokens_per_run} onChange={(v) => setCost('max_tokens_per_run', Number(v))} min={0} />
                        <Field id="daily_ceiling" label="Daily cap (USD)" value={settings.cost_budget.daily_cost_ceiling} onChange={(v) => setCost('daily_cost_ceiling', Number(v))} min={0} step={0.01} />
                        <Field id="weekly_ceiling" label="Weekly cap (USD)" value={settings.cost_budget.weekly_cost_ceiling} onChange={(v) => setCost('weekly_cost_ceiling', Number(v))} min={0} step={0.01} />
                        <Field id="cooldown" label="Cooldown (sec)" value={settings.cost_budget.cooldown_seconds} onChange={(v) => setCost('cooldown_seconds', Number(v))} min={0} />
                      </div>
                    </section>
                    {settings.system_health && settings.system_health.budget_status.length > 0 ? (
                      <section className="flex flex-col gap-6">
                        <SettingSectionTitle>Current usage (today)</SettingSectionTitle>
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
                        <SettingSectionTitle>Current usage (today)</SettingSectionTitle>
                        <p
                          className="m-0 text-[13px] font-normal text-oxford/[0.35] italic leading-relaxed max-w-xl"
                          style={{ fontFamily: FONT_GEIST }}
                        >
                          No usage yet.
                        </p>
                      </section>
                    )}
                  </div>
                )}

                {/* ——— Pipeline ——— */}
                {activeTab === 'pipeline' && (
                  <div className="flex flex-col gap-8 min-h-0">
                    <DescText>
                      Changes apply on next run. Advance, pass, and escalations always need a human.
                    </DescText>
                    <section className="flex flex-col gap-6">
                      <SettingSectionTitle>Stages</SettingSectionTitle>
                      <DescText>Scouts find companies, Reviewers score, Partners decide.</DescText>
                      <div className="flex flex-col gap-6">
                        <Toggle id="scouts_enabled" checked={settings.agent_config.scouts_enabled} onChange={(v) => setAgent('scouts_enabled', v)} label="Scouts" />
                        <Toggle id="reviewers_enabled" checked={settings.agent_config.reviewers_enabled} onChange={(v) => setAgent('reviewers_enabled', v)} label="Reviewers" />
                        <Toggle id="partners_enabled" checked={settings.agent_config.partners_enabled} onChange={(v) => setAgent('partners_enabled', v)} label="Partners" />
                      </div>
                    </section>
                    <section className="flex flex-col gap-6">
                      <SettingSectionTitle>Per run</SettingSectionTitle>
                      <DescText>Companies per run and confidence threshold for decisions.</DescText>
                      <div className="flex flex-col gap-6">
                        <Field id="max_agents" label="Companies per run" value={settings.agent_config.max_agents_per_run} onChange={(v) => setAgent('max_agents_per_run', Number(v))} min={1} />
                        <SettingRow id="confidence_threshold" label="Confidence (0–1)">
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
                            style={{ fontFamily: FONT_GEIST }}
                            aria-label="Confidence 0 to 1"
                          />
                        </SettingRow>
                      </div>
                    </section>
                  </div>
                )}

                {/* ——— Discovery ——— */}
                {activeTab === 'discovery' && (
                  <div className="flex flex-col gap-8 min-h-0">
                    <section className="flex flex-col gap-6">
                      <SettingSectionTitle>Source</SettingSectionTitle>
                      <DescText>Where scouts look for companies.</DescText>
                      <div className="flex flex-col gap-6">
                        <SettingRow id="scout_region" label="Region">
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
                        <Toggle id="scout_serp_enabled" checked={settings.agent_config.scout_serp_enabled} onChange={(v) => setAgent('scout_serp_enabled', v)} label="Use web search (SERP)" />
                        <Field id="scout_serp_budget" label="SERP daily budget" value={settings.agent_config.scout_serp_daily_budget} onChange={(v) => setAgent('scout_serp_daily_budget', Number(v))} min={0} />
                      </div>
                    </section>
                  </div>
                )}

                {/* ——— Meta-agent ——— */}
                {activeTab === 'meta' && settings.meta_agent && (
                  <div className="flex flex-col gap-8 min-h-0">
                    <section className="flex flex-col gap-6">
                      <SettingSectionTitle>Meta-agent</SettingSectionTitle>
                      <DescText>Tunes pipeline config over time (e.g. scout weights, confidence).</DescText>
                      <Toggle
                        id="meta_enabled"
                        checked={settings.meta_agent.enabled}
                        onChange={(v) => setSettings((s) => s ? { ...s, meta_agent: { ...(s.meta_agent ?? settings.meta_agent!), enabled: v } } : s)}
                        label="Enable meta-agent"
                      />
                    </section>
                    <section className="flex flex-col gap-6">
                      <SettingSectionTitle>Schedule & thresholds</SettingSectionTitle>
                      <div className="flex flex-col gap-6">
                        <Field id="meta_interval" label="Run every (sec)" value={settings.meta_agent.interval_seconds} onChange={(v) => setSettings((s) => s ? { ...s, meta_agent: { ...(s.meta_agent ?? settings.meta_agent!), interval_seconds: Number(v) } } : s)} min={0} />
                        <Field id="meta_min_reviews" label="Min reviews" value={settings.meta_agent.min_reviews} onChange={(v) => setSettings((s) => s ? { ...s, meta_agent: { ...(s.meta_agent ?? settings.meta_agent!), min_reviews: Number(v) } } : s)} min={0} />
                        <Field id="meta_min_decisions" label="Min decisions" value={settings.meta_agent.min_decisions} onChange={(v) => setSettings((s) => s ? { ...s, meta_agent: { ...(s.meta_agent ?? settings.meta_agent!), min_decisions: Number(v) } } : s)} min={0} />
                        <Field id="meta_cooldown" label="Cooldown (cycles)" value={settings.meta_agent.mutation_cooldown_cycles} onChange={(v) => setSettings((s) => s ? { ...s, meta_agent: { ...(s.meta_agent ?? settings.meta_agent!), mutation_cooldown_cycles: Number(v) } } : s)} min={0} />
                      </div>
                    </section>
                  </div>
                )}

                {/* ——— Portfolio ——— */}
                {activeTab === 'portfolio' && (
                  <div className="flex flex-col gap-8 min-h-0">
                    <section className="flex flex-col gap-6">
                      <SettingSectionTitle>Watchlist</SettingSectionTitle>
                      <DescText>Auto-add companies by signal strength.</DescText>
                      <Toggle id="auto_watchlist" checked={settings.portfolio.auto_watchlist} onChange={(v) => setPortfolio('auto_watchlist', v)} label="Auto-add to watchlist" />
                    </section>
                    <section className="flex flex-col gap-6">
                      <SettingSectionTitle>Updates & memos</SettingSectionTitle>
                      <DescText>Signal scan frequency and memo detail.</DescText>
                      <div className="flex flex-col gap-6">
                        <SettingRow id="signal_scan" label="Signal scan">
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
                        <SettingRow id="memo_verbosity" label="Memo detail">
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
                  </motion.div>
                </AnimatePresence>
              </div>
            </div>
          </PanelShell>
        </div>
        </motion.div>
      </main>
    </div>
  );
}
