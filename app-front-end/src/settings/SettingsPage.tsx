import { useState, useEffect, type ReactNode } from 'react';
import { Link, useNavigate } from 'react-router';
import { useClerk } from '@clerk/react-router';
import { UserProfile } from '@clerk/react';
import { motion, AnimatePresence } from 'framer-motion';
import SystemBar from '../components/SystemBar';
import MobileHeader from '../components/MobileHeader';
import PanelShell from '../components/PanelShell';
import LoadingAnimation from '../components/LoadingAnimation';
import { fetchSettings, patchSettings, type AgentBudgetStatus, type Settings, type FundIdentity } from '../api/settings';
import { fetchMe } from '../api/me';
import { fetchAgentsStatus, type AgentsStatus } from '../api/agents';
import { tokens } from '../design-system/tokens';
import { userProfileAppearance } from '../design-system/clerk-appearance';
import { useMediaQuery } from '../hooks';

type TabId = 'account' | 'budget' | 'pipeline' | 'discovery' | 'meta' | 'portfolio';

const inputCls =
  'w-full min-w-0 max-w-[10rem] border-0 border-b bg-transparent type-body-sm text-oxford placeholder:text-oxford/40 py-1.5 outline-none rounded-none btn-interaction';
const inputBorder = 'border-oxford/25 focus:border-oxford/25';
const hintCls = 'block type-body-sm text-oxford/40 mt-0.5 mb-0 leading-relaxed';
const selectCls = inputCls + ' border-oxford/25 focus:border-oxford/25 cursor-pointer appearance-none pr-8 max-w-full';
const toggleLabelCls = 'type-body-sm text-oxford';
const groupHeadingCls = 'type-label-section text-oxford/60 mb-1';
const sectionIntroCls = 'type-body-sm text-oxford/60 mb-1.5 max-w-xl leading-snug';

const TOGGLE_TRACK = 'h-6 w-11 shrink-0 rounded-full cursor-pointer inline-flex items-center';
const TOGGLE_KNOB = 'h-4 w-4 rounded-full shadow-sm pointer-events-none block';

/** Single setting row: label (and hint) left, control right. Use for consistent alignment across tabs. */
function SettingRow({
  label,
  hint,
  children,
  id,
}: { label: string; hint?: string; children: ReactNode; id?: string }) {
  return (
    <div className="grid grid-cols-[minmax(0,200px)_1fr] gap-x-6 gap-y-0.5 items-center py-2 min-h-[2.5rem]">
      <div className="min-w-0">
        {id ? (
          <label htmlFor={id} className={toggleLabelCls}>{label}</label>
        ) : (
          <span className={toggleLabelCls}>{label}</span>
        )}
        {hint && <p className={hintCls}>{hint}</p>}
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
      className={`${inputCls} ${inputBorder}`}
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
      { id: 'budget', label: 'Budget' },
      { id: 'pipeline', label: 'Pipeline' },
      { id: 'discovery', label: 'Discovery' },
      { id: 'meta', label: 'Meta-agent' },
      { id: 'portfolio', label: 'Portfolio' },
      { id: 'account', label: 'Account' },
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
  const fundIdentity = settings?.fund_identity ?? { fund_name: '', stage_focus: '', geographic_focus: '' };
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
                  transition={{ duration: tokens.motion.duration.micro, ease: tokens.motion.ease }}
                  className="px-4 pb-0 border-b border-oxford/[0.06] type-label-tab bg-oxford overflow-hidden text-ivory/70"
                  aria-label="Menu"
                >
                  <div className="flex flex-col items-start gap-3 py-3">
                    <Link to="/v1" className="type-label-section text-ivory/70 hover:text-ivory btn-interaction" onClick={() => setMobileMenuOpen(false)}>
                      Overview
                    </Link>
                    <button type="button" onClick={handleLogout} className="type-label-section text-ivory/50 hover:text-ivory btn-interaction text-left">
                      Log out
                    </button>
                  </div>
                </motion.section>
              )}
            </AnimatePresence>
          </>
        )}
        <SystemBar scoutCount={0} navLink={{ href: '/', label: 'Home' }} />
        <main className="flex-1 min-h-0 flex flex-col items-center justify-center gap-3 px-4 pt-4 lg:pl-[13rem] lg:pr-6 lg:pt-6">
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
                transition={{ duration: tokens.motion.duration.micro, ease: tokens.motion.ease }}
                className="px-4 pb-0 border-b border-oxford/[0.06] type-label-tab bg-oxford overflow-hidden text-ivory/70"
                aria-label="Menu"
              >
                <div className="flex flex-col items-start gap-3 py-3">
                  {/* Nav links */}
                  <div className="flex flex-col items-start gap-1">
                    <Link
                      to="/v1"
                      className="type-label-section text-ivory/70 hover:text-ivory btn-interaction"
                      onClick={() => setMobileMenuOpen(false)}
                    >
                      Overview
                    </Link>
                    <span className="type-label-section text-ivory">
                      Settings
                    </span>
                  </div>

                  {/* Username / logout */}
                  <div className="flex flex-col items-start gap-1 mt-3">
                    {displayName && (
                      <span
                        className="type-label-section text-ivory/60"
                      >
                        {displayName}
                      </span>
                    )}
                    <button
                      type="button"
                      onClick={handleLogout}
                      className="type-label-section text-ivory/50 hover:text-ivory btn-interaction"
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
      <main className="flex-1 flex flex-col min-h-0 overflow-hidden px-4 pt-4 lg:pl-[13rem] lg:pr-6 lg:pt-6 pb-3 lg:pb-4">
        <motion.div
          className="flex-1 flex flex-col min-h-0 overflow-hidden"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: tokens.motion.duration.short, ease: tokens.motion.ease }}
        >
        <header className="flex-none mb-4 hidden lg:block">
          <h1
            className="type-hero font-bold text-oxford"
          >
            Aethria
          </h1>
        </header>
        {/* Bordered grid: static border; only inner content scrolls (WorkGrid pattern). */}
        <div className="flex-1 min-h-0 flex flex-col overflow-hidden w-full min-w-0 rounded-none border border-oxford/[0.06] bg-paper">
          <PanelShell
            title="Settings"
            actions={
              <div className="flex items-center gap-3">
                {saveSuccess && (
                  <p className="type-label-section text-oxford/60" role="status" aria-live="polite">
                    Saved
                  </p>
                )}
                <button
                  type="button"
                  onClick={handleSave}
                  disabled={saving}
                  className="type-label-tab text-oxford/60 hover:text-oxford btn-interaction focus:outline-none focus-visible:ring-2 focus-visible:ring-oxford/40 focus-visible:ring-inset"
                >
                  {saving ? 'Saving…' : 'Save'}
                </button>
              </div>
            }
            tabs={tabs.map(({ id, label }) => ({ id, label }))}
            activeTab={activeTab}
            onTabChange={(id) => setActiveTab(id as TabId)}
            contentOverflowHidden
            contentClassName="flex-1 min-h-0 flex flex-col overflow-hidden w-full min-w-0"
          >
            {validationErrors.length > 0 && (
              <div className="flex-none px-4 sm:px-6 py-2 border-b border-oxford/25 bg-warning">
                <p className="type-label-section text-oxford/80 mb-1">Validation errors</p>
                <ul className="type-body-sm text-oxford/80 space-y-0.5">
                  {validationErrors.map((e, i) => <li key={i}>{e}</li>)}
                </ul>
              </div>
            )}
            <div className="flex-1 min-h-0 overflow-hidden p-4 sm:p-6">
              <div className="h-full flex flex-col gap-4 overflow-hidden">
                <AnimatePresence mode="wait">
                  <motion.div
                    key={activeTab}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    transition={{ duration: tokens.motion.duration.short, ease: tokens.motion.ease }}
                    className="flex flex-col gap-4 min-h-0 overflow-hidden h-full"
                  >
                {/* ——— Account ——— */}
                {activeTab === 'account' && (
                  <div className="flex-1 min-h-0 overflow-y-auto flex flex-col gap-4">
                    {agentsStatus && !agentsStatus.agents_will_run && (
                      <section>
                        <h3 className={groupHeadingCls}>Agents may not run on this server</h3>
                        <p className={sectionIntroCls}>
                          Set <code className="type-meta bg-oxford/[0.06] px-1 rounded">USE_SUPABASE_STORAGE=1</code>, <code className="type-meta bg-oxford/[0.06] px-1 rounded">OPENAI_API_KEY</code>, <code className="type-meta bg-oxford/[0.06] px-1 rounded">SUPABASE_URL</code>, <code className="type-meta bg-oxford/[0.06] px-1 rounded">SUPABASE_SERVICE_ROLE_KEY</code> in your host environment. See AGENTS.md.
                        </p>
                        <p className="type-meta text-oxford/60">
                          Worker: {agentsStatus.worker_ready ? 'ready' : 'not ready'} · Supabase: {agentsStatus.supabase_configured ? 'ok' : 'missing'} · OpenAI: {agentsStatus.openai_configured ? 'ok' : 'missing'}
                        </p>
                      </section>
                    )}
                    <section>
                      <h3 className={groupHeadingCls}>Fund identity</h3>
                      <p className={sectionIntroCls}>
                        Shown on the dashboard (desktop). Fund name, stage focus, and geographic focus.
                      </p>
                      <Field id="fund_name" label="Fund name" value={fundIdentity.fund_name} onChange={(v) => setFundIdentity('fund_name', String(v))} type="text" />
                      <Field id="stage_focus" label="Stage focus" value={fundIdentity.stage_focus} onChange={(v) => setFundIdentity('stage_focus', String(v))} type="text" />
                      <Field id="geographic_focus" label="Geographic focus" value={fundIdentity.geographic_focus} onChange={(v) => setFundIdentity('geographic_focus', String(v))} type="text" />
                    </section>
                    {userId && (
                      <section>
                        <h3 className={groupHeadingCls}>Your user ID</h3>
                        <p className={sectionIntroCls}>
                          Clerk user ID; used for startups, settings, and agents. For <code className="type-meta bg-oxford/[0.06] px-1 rounded">run.py</code> agents, set <code className="type-meta bg-oxford/[0.06] px-1 rounded">AETHRIA_AGENT_USER_ID</code> to this in backend .env.
                        </p>
                        <div className="flex items-center gap-2 flex-wrap">
                          <code className="type-meta text-oxford/80 bg-oxford/[0.06] px-2 py-1 rounded select-none" aria-hidden="true">
                            {userId.replace(/./g, '•')}
                          </code>
                          <button
                            type="button"
                            onClick={() => navigator.clipboard?.writeText(userId).then(() => { setUserIdCopied(true); setTimeout(() => setUserIdCopied(false), 2000); })}
                            className="type-label-section text-oxford/60 hover:text-oxford border border-oxford/25 px-2 py-1 rounded"
                          >
                            {userIdCopied ? 'Copied' : 'Copy'}
                          </button>
                        </div>
                      </section>
                    )}
                    <section>
                      <h3 className={groupHeadingCls}>Account & security</h3>
                      <p className={sectionIntroCls}>
                        Change password, update email, or manage security and sessions.
                      </p>
                      <div className="aethria-clerk-profile min-h-[320px] border border-oxford/[0.06] bg-paper">
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
                  <div className="flex flex-col gap-4 min-h-0">
                    <section>
                      <h3 className={groupHeadingCls}>Budget</h3>
                      <p className={sectionIntroCls}>Enable to enforce token and cost limits.</p>
                      <Toggle id="cost_budget_enabled" checked={settings.cost_budget?.enabled ?? false} onChange={(v) => setCost('enabled', v)} label="Enable cost budget" />
                    </section>
                    <section>
                      <h3 className={groupHeadingCls}>Limits</h3>
                      <p className={sectionIntroCls}>Caps and cooldown after a limit is hit.</p>
                      <Field id="max_tokens" label="Tokens per run" value={settings.cost_budget.max_tokens_per_run} onChange={(v) => setCost('max_tokens_per_run', Number(v))} min={0} />
                      <Field id="daily_ceiling" label="Daily cap (USD)" value={settings.cost_budget.daily_cost_ceiling} onChange={(v) => setCost('daily_cost_ceiling', Number(v))} min={0} step={0.01} />
                      <Field id="weekly_ceiling" label="Weekly cap (USD)" value={settings.cost_budget.weekly_cost_ceiling} onChange={(v) => setCost('weekly_cost_ceiling', Number(v))} min={0} step={0.01} />
                      <Field id="cooldown" label="Cooldown (sec)" value={settings.cost_budget.cooldown_seconds} onChange={(v) => setCost('cooldown_seconds', Number(v))} min={0} />
                    </section>
                    {settings.system_health && settings.system_health.budget_status.length > 0 ? (
                      <section>
                        <h3 className={groupHeadingCls}>Current usage (today)</h3>
                        <div className="flex flex-col gap-2 max-w-md">
                          {settings.system_health.budget_status.map((b: AgentBudgetStatus) => {
                            const callsPct = b.daily_calls_limit > 0 ? (b.daily_calls_used / b.daily_calls_limit) : 0;
                            const tokensPct = b.daily_tokens_limit > 0 ? (b.daily_tokens_used / b.daily_tokens_limit) : 0;
                            const callsWidth = `${Math.min(100, callsPct * 100)}%`;
                            const tokensWidth = `${Math.min(100, tokensPct * 100)}%`;
                            return (
                              <div key={b.agent_id} className="border border-oxford/[0.06] p-2 space-y-1">
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
                      <section>
                        <h3 className={groupHeadingCls}>Current usage (today)</h3>
                        <p className={sectionIntroCls}>No usage yet.</p>
                      </section>
                    )}
                  </div>
                )}

                {/* ——— Pipeline ——— */}
                {activeTab === 'pipeline' && (
                  <div className="flex flex-col gap-4 min-h-0">
                    <p className={sectionIntroCls}>
                      Changes apply on next run. Advance, pass, and escalations always need a human.
                    </p>
                    <section>
                      <h3 className={groupHeadingCls}>Stages</h3>
                      <p className={sectionIntroCls}>Scouts find companies, Reviewers score, Partners decide.</p>
                      <Toggle id="scouts_enabled" checked={settings.agent_config.scouts_enabled} onChange={(v) => setAgent('scouts_enabled', v)} label="Scouts" />
                      <Toggle id="reviewers_enabled" checked={settings.agent_config.reviewers_enabled} onChange={(v) => setAgent('reviewers_enabled', v)} label="Reviewers" />
                      <Toggle id="partners_enabled" checked={settings.agent_config.partners_enabled} onChange={(v) => setAgent('partners_enabled', v)} label="Partners" />
                    </section>
                    <section>
                      <h3 className={groupHeadingCls}>Per run</h3>
                      <p className={sectionIntroCls}>Companies per run and confidence threshold for decisions.</p>
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
                          className={`${inputCls} ${inputBorder}`}
                          aria-label="Confidence 0 to 1"
                        />
                      </SettingRow>
                    </section>
                  </div>
                )}

                {/* ——— Discovery ——— */}
                {activeTab === 'discovery' && (
                  <div className="flex flex-col gap-4 min-h-0">
                    <section>
                      <h3 className={groupHeadingCls}>Source</h3>
                      <p className={sectionIntroCls}>Where scouts look for companies.</p>
                      <SettingRow id="scout_region" label="Region">
                        <select id="scout_region" value={settings.agent_config.scout_region} onChange={(e) => setAgent('scout_region', e.target.value)} className={selectCls}>
                          <option value="europe">Europe</option>
                          <option value="global">Global</option>
                        </select>
                      </SettingRow>
                      <Toggle id="scout_serp_enabled" checked={settings.agent_config.scout_serp_enabled} onChange={(v) => setAgent('scout_serp_enabled', v)} label="Use web search (SERP)" />
                      <Field id="scout_serp_budget" label="SERP daily budget" value={settings.agent_config.scout_serp_daily_budget} onChange={(v) => setAgent('scout_serp_daily_budget', Number(v))} min={0} />
                    </section>
                  </div>
                )}

                {/* ——— Meta-agent ——— */}
                {activeTab === 'meta' && settings.meta_agent && (
                  <div className="flex flex-col gap-4 min-h-0">
                    <section>
                      <h3 className={groupHeadingCls}>Meta-agent</h3>
                      <p className={sectionIntroCls}>Tunes pipeline config over time (e.g. scout weights, confidence).</p>
                      <Toggle
                        id="meta_enabled"
                        checked={settings.meta_agent.enabled}
                        onChange={(v) => setSettings((s) => s ? { ...s, meta_agent: { ...(s.meta_agent ?? settings.meta_agent!), enabled: v } } : s)}
                        label="Enable meta-agent"
                      />
                    </section>
                    <section>
                      <h3 className={groupHeadingCls}>Schedule & thresholds</h3>
                      <Field id="meta_interval" label="Run every (sec)" value={settings.meta_agent.interval_seconds} onChange={(v) => setSettings((s) => s ? { ...s, meta_agent: { ...(s.meta_agent ?? settings.meta_agent!), interval_seconds: Number(v) } } : s)} min={0} />
                      <Field id="meta_min_reviews" label="Min reviews" value={settings.meta_agent.min_reviews} onChange={(v) => setSettings((s) => s ? { ...s, meta_agent: { ...(s.meta_agent ?? settings.meta_agent!), min_reviews: Number(v) } } : s)} min={0} />
                      <Field id="meta_min_decisions" label="Min decisions" value={settings.meta_agent.min_decisions} onChange={(v) => setSettings((s) => s ? { ...s, meta_agent: { ...(s.meta_agent ?? settings.meta_agent!), min_decisions: Number(v) } } : s)} min={0} />
                      <Field id="meta_cooldown" label="Cooldown (cycles)" value={settings.meta_agent.mutation_cooldown_cycles} onChange={(v) => setSettings((s) => s ? { ...s, meta_agent: { ...(s.meta_agent ?? settings.meta_agent!), mutation_cooldown_cycles: Number(v) } } : s)} min={0} />
                    </section>
                  </div>
                )}

                {/* ——— Portfolio ——— */}
                {activeTab === 'portfolio' && (
                  <div className="flex flex-col gap-4 min-h-0">
                    <section>
                      <h3 className={groupHeadingCls}>Watchlist</h3>
                      <p className={sectionIntroCls}>Auto-add companies by signal strength.</p>
                      <Toggle id="auto_watchlist" checked={settings.portfolio.auto_watchlist} onChange={(v) => setPortfolio('auto_watchlist', v)} label="Auto-add to watchlist" />
                    </section>
                    <section>
                      <h3 className={groupHeadingCls}>Updates & memos</h3>
                      <p className={sectionIntroCls}>Signal scan frequency and memo detail.</p>
                      <SettingRow id="signal_scan" label="Signal scan">
                        <select id="signal_scan" value={settings.portfolio.signal_scan_frequency} onChange={(e) => setPortfolio('signal_scan_frequency', e.target.value)} className={selectCls}>
                          <option value="hourly">Hourly</option>
                          <option value="every_6h">Every 6 hours</option>
                          <option value="daily">Daily</option>
                        </select>
                      </SettingRow>
                      <SettingRow id="memo_verbosity" label="Memo detail">
                        <select id="memo_verbosity" value={settings.portfolio.memo_verbosity} onChange={(e) => setPortfolio('memo_verbosity', e.target.value)} className={selectCls}>
                          <option value="minimal">Brief</option>
                          <option value="standard">Standard</option>
                          <option value="full">Full</option>
                        </select>
                      </SettingRow>
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
