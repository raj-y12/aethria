import { useState, useEffect, type CSSProperties } from 'react';
import { Link, useNavigate } from 'react-router';
import { useClerk } from '@clerk/react-router';
import { useQueryClient } from '@tanstack/react-query';
import { UserProfile } from '@clerk/react';
import { motion, AnimatePresence } from 'framer-motion';
import SystemBar from '../components/SystemBar';
import MobileHeader from '../components/MobileHeader';
import LoadingAnimation from '../components/LoadingAnimation';
import AgentLogoutModal from '../components/AgentLogoutModal';
import { fetchSettings, patchSettings, type AgentBudgetStatus, type Settings, type FundIdentity } from '../api/settings';
import { fetchMe } from '../api/me';
import { fetchAgentsStatus, toggleAgents, type AgentsStatus } from '../api/agents';
import { useAgentsEnabled } from '../hooks/useAgentsEnabled';
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

const SELECT_CHEVRON =
  "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='10' viewBox='0 0 10 10'%3E%3Cpath fill='%23002147' fill-opacity='0.4' d='M0 3h10L5 8z'/%3E%3C/svg%3E\")";

const inputCls =
  'w-full bg-transparent border-0 border-b border-oxford/10 rounded-none shadow-none outline-none focus:border-oxford/30 transition-colors duration-300 type-body text-oxford py-phi-2 px-0 placeholder:text-oxford/20 [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none [-moz-appearance:textfield]';
const selectCls = `${inputCls} cursor-pointer pr-8 bg-no-repeat bg-[length:10px] bg-[center_right_2px] appearance-none`;
const selectStyle: CSSProperties = { backgroundImage: SELECT_CHEVRON };
const labelCls = 'type-meta uppercase tracking-[0.14em] text-oxford/35';
const hintCls = 'type-meta text-oxford/45 mt-0.5';
const btnCls = 'type-meta uppercase tracking-[0.12em] text-oxford/40 hover:text-oxford disabled:opacity-30 transition-colors btn-interaction cursor-pointer bg-transparent border-0 p-0';
const outlineBtnCls = 'type-meta uppercase tracking-[0.12em] text-oxford/50 hover:text-oxford disabled:opacity-30 transition-colors btn-interaction cursor-pointer bg-transparent border-0 p-0';

const TABS: { id: TabId; label: string }[] = [
  { id: 'fund',      label: 'Fund'      },
  { id: 'pipeline',  label: 'Pipeline'  },
  { id: 'discovery', label: 'Discovery' },
  { id: 'portfolio', label: 'Portfolio' },
  { id: 'budget',    label: 'Budget'    },
  { id: 'account',   label: 'Account'   },
];

/* ── Primitives ─────────────────────────────────────────────────── */

function TextField({ id, label, value, onChange, hint, type = 'text', min, step }: {
  id: string; label: string; value: string | number; hint?: string;
  onChange: (v: string | number) => void; type?: 'text' | 'number'; min?: number; step?: number;
}) {
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className={labelCls}>{label}</label>
      {hint && <span className={hintCls}>{hint}</span>}
      <input id={id} type={type} min={min} step={step} value={value}
        onChange={(e) => onChange(type === 'number' ? Number(e.target.value) || 0 : e.target.value)}
        className={inputCls} />
    </div>
  );
}

function SelectField({ id, label, value, onChange, children }: {
  id: string; label: string; value: string; onChange: (v: string) => void; children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className={labelCls}>{label}</label>
      <select id={id} value={value} onChange={(e) => onChange(e.target.value)} className={selectCls} style={selectStyle}>
        {children}
      </select>
    </div>
  );
}

function ToggleRow({ id, checked, onChange, label, hint }: {
  id: string; checked: boolean; onChange: (v: boolean) => void; label: string; hint?: string;
}) {
  return (
    <div className="flex items-center justify-between gap-8 py-3">
      <div className="flex flex-col gap-0.5 min-w-0">
        <label htmlFor={id} className="type-body-sm text-oxford cursor-pointer">{label}</label>
        {hint && <span className="type-meta text-oxford/30 leading-snug">{hint}</span>}
      </div>
      <button id={id} type="button" role="switch" aria-checked={checked} onClick={() => onChange(!checked)}
        className={`shrink-0 h-6 w-11 inline-flex items-center overflow-hidden rounded-none btn-interaction transition-colors duration-300 ${checked ? 'bg-oxford' : 'bg-oxford/[0.07]'}`}
        style={{ transitionTimingFunction: tokens.motion.easeCss }}>
        <span className={`h-4 w-4 rounded-none pointer-events-none block transition-transform duration-200 ${checked ? 'translate-x-5 bg-paper' : 'translate-x-1 bg-oxford/35'}`} aria-hidden />
      </button>
    </div>
  );
}

/* ── Page ────────────────────────────────────────────────────────── */

export default function SettingsPage() {
  const navigate = useNavigate();
  const { signOut } = useClerk();
  const queryClient = useQueryClient();
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
  const agentsEnabled = useAgentsEnabled();
  const [showLogoutModal, setShowLogoutModal] = useState(false);

  const doLogout = () => {
    localStorage.removeItem('aethria_last_activity');
    sessionStorage.removeItem('auth');
    sessionStorage.removeItem('authUser');
    signOut?.().then(() => navigate('/sign-in', { replace: true }));
  };
  const handleLogout = () => setShowLogoutModal(true);
  const handleTurnOffAndLogout = async () => { await toggleAgents(false); doLogout(); };
  const handleTurnOnAndStay  = async () => { await toggleAgents(true);  doLogout(); };

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
    setThesisLoadError(null); setThesisLoading(true);
    fetchFundThesisSummary()
      .then((s) => { setThesisSummary(s); if (s) { setThesisDraft(s.raw_text ?? ''); setThesisActivateId(s.versions.find((v) => v.is_active)?.id ?? ''); } })
      .catch((e: unknown) => { setThesisSummary(null); setThesisLoadError(e instanceof Error ? e.message : 'Failed'); })
      .finally(() => setThesisLoading(false));
  };

  useEffect(() => { if (activeTab !== 'fund' || !agentsStatus?.supabase_configured) return; reloadThesis(); }, [activeTab, agentsStatus?.supabase_configured]);
  useEffect(() => { if (!thesisReprocessToast) return; const t = window.setTimeout(() => setThesisReprocessToast(null), 6500); return () => window.clearTimeout(t); }, [thesisReprocessToast]);
  useEffect(() => { let c = false; fetchMe().then((me) => { if (!c && me) setUserId(me.user_id); }); return () => { c = true; }; }, []);
  useEffect(() => { let c = false; fetchAgentsStatus().then((s) => { if (!c) setAgentsStatus(s ?? null); }); return () => { c = true; }; }, []);
  useEffect(() => {
    let c = false;
    fetchSettings()
      .then((d) => { if (!c) { setSettings(d); setLoadError(null); } })
      .catch((e: unknown) => { if (!c) { setSettings(null); setLoadError(e instanceof Error ? e.message : 'Failed'); } })
      .finally(() => { if (!c) setLoading(false); });
    return () => { c = true; };
  }, []);

  const handleSave = async () => {
    if (!settings) return;
    setSaving(true); setValidationErrors([]); setSaveSuccess(false);
    const result = await patchSettings(settings);
    setSaving(false);
    if (result.error) { setValidationErrors(result.error.errors); return; }
    setSaveSuccess(true);
    if (result.data) setSettings(result.data);
    await queryClient.invalidateQueries({ queryKey: ['settings'] });
  };

  const setCost = <K extends keyof Settings['cost_budget']>(k: K, v: Settings['cost_budget'][K]) =>
    setSettings((s) => s ? { ...s, cost_budget: { ...s.cost_budget, [k]: v } } : s);
  const setAgent = <K extends keyof Settings['agent_config']>(k: K, v: Settings['agent_config'][K]) =>
    setSettings((s) => s ? { ...s, agent_config: { ...s.agent_config, [k]: v } } : s);
  const setPortfolio = <K extends keyof Settings['portfolio']>(k: K, v: Settings['portfolio'][K]) =>
    setSettings((s) => s ? { ...s, portfolio: { ...s.portfolio, [k]: v } } : s);
  const fundIdentity = settings?.fund_identity ?? { fund_name: '', stage_focus: '', geographic_focus: '', canonical_website: '' };
  const setFundIdentity = <K extends keyof FundIdentity>(k: K, v: string) =>
    setSettings((s) => s ? { ...s, fund_identity: { ...(s.fund_identity ?? fundIdentity), [k]: v } } : s);

  if (loading) return <LoadingAnimation />;

  const mobileMenu = (
    <AnimatePresence>
      {mobileMenuOpen && (
        <motion.section id="mobile-menu"
          initial={{ gridTemplateRows: '0fr', opacity: 0 }} animate={{ gridTemplateRows: '1fr', opacity: 1 }} exit={{ gridTemplateRows: '0fr', opacity: 0 }}
          transition={transitionOrReduced(reduceMotion, { duration: tokens.motion.duration.micro, ease: tokens.motion.ease })}
          style={{ display: 'grid' }}
          className="border-b border-hairline bg-oxford" aria-label="Menu">
          <div className="min-h-0 overflow-hidden px-4 pb-0">
          <div className="flex flex-col items-start gap-3 py-3">
            <Link to="/v1" className="type-label-section text-white/70 hover:text-white btn-interaction" onClick={() => setMobileMenuOpen(false)}>Overview</Link>
            {displayName && <span className="type-label-section text-white/60">{displayName}</span>}
            <button type="button" onClick={handleLogout} className="type-label-section text-white/50 hover:text-white btn-interaction">Log out</button>
          </div>
          </div>
        </motion.section>
      )}
    </AnimatePresence>
  );

  if (!settings) {
    return (
      <div className="h-screen w-full flex flex-col overflow-hidden bg-paper">
        {!isDesktop && <><MobileHeader onMenuToggle={() => setMobileMenuOpen((o) => !o)} />{mobileMenu}</>}
        <SystemBar navLink={{ href: '/', label: 'Home' }} />
        <main className="flex-1 flex items-center justify-center px-8 lg:pl-[calc(9rem+3rem)]">
          <div className="flex flex-col gap-2">
            <p className={labelCls}>Failed to load settings</p>
            {loadError && <p className="type-body-sm text-oxford/50">{loadError}</p>}
          </div>
        </main>
      </div>
    );
  }

  return (
    <div className="h-screen w-full flex flex-col overflow-hidden bg-paper">
      {!isDesktop && <><MobileHeader onMenuToggle={() => setMobileMenuOpen((o) => !o)} />{mobileMenu}</>}
      <SystemBar agentConfig={settings.agent_config} navLink={{ href: '/', label: 'Home' }} />

      {/* Full-height canvas offset by SystemBar */}
      <div className="flex-1 flex flex-col min-h-0 lg:pl-36">

        {/* Top bar: page title + save */}
        <div className="flex-none flex items-center justify-between px-8 py-4">
          <span className={labelCls}>Settings</span>
          <div className="flex items-center gap-4">
            {saveSuccess && <span className="type-meta text-oxford/30" role="status" aria-live="polite">Saved</span>}
            {validationErrors.length > 0 && <span className="type-meta text-escalation/60">{validationErrors[0]}</span>}
            <button type="button" onClick={handleSave} disabled={saving} className={btnCls}>
              {saving ? 'Saving…' : 'Save'}
            </button>
          </div>
        </div>

        {/* Tab bar — exact FilterButton style from WorkGrid */}
        <div className="flex-none flex items-center gap-1 px-5 overflow-x-auto">
          {TABS.map(({ id, label }) => (
            <button key={id} type="button" onClick={() => setActiveTab(id)}
              className={`type-label-tab px-3 py-1.5 transition-all duration-300 border-b whitespace-nowrap ${
                activeTab === id ? 'border-oxford text-oxford bg-oxford/5' : 'border-transparent text-oxford/30 hover:text-oxford/60'
              }`}>
              {label}
            </button>
          ))}
        </div>

        {/* Full-width content */}
        <div className="flex-1 min-w-0 min-h-0 overflow-hidden">
            <AnimatePresence mode="wait">
              <motion.div key={activeTab}
                initial={reduceMotion ? { opacity: 1 } : { opacity: 0 }}
                animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                transition={transitionOrReduced(reduceMotion, { duration: tokens.motion.duration.short, ease: tokens.motion.ease })}
                className="h-full overflow-y-auto px-8 py-8">

                {/* ── Fund ── */}
                {activeTab === 'fund' && (
                  <div className="flex flex-col gap-12">

                    <div className="flex flex-col gap-6">
                      <p className={labelCls}>Fund identity</p>
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-6 max-w-2xl">
                        <TextField id="fund_name" label="Fund name" value={fundIdentity.fund_name} onChange={(v) => setFundIdentity('fund_name', String(v))} />
                        <TextField id="stage_focus" label="Stage focus" hint="e.g. Pre-seed, Seed, Series A" value={fundIdentity.stage_focus} onChange={(v) => setFundIdentity('stage_focus', String(v))} />
                        <TextField id="geographic_focus" label="Geographic focus" hint="e.g. Europe, UK, Global" value={fundIdentity.geographic_focus} onChange={(v) => setFundIdentity('geographic_focus', String(v))} />
                        <TextField id="canonical_website" label="Fund website" value={fundIdentity.canonical_website ?? ''} onChange={(v) => setFundIdentity('canonical_website', String(v))} />
                      </div>
                    </div>

                    <div className="flex flex-col gap-6">
                      <p className={labelCls}>Investment mandate</p>
                      {!agentsStatus?.supabase_configured ? (
                        <p className="type-body-sm text-oxford/40">Requires Supabase — set <code className="bg-oxford/[0.05] px-1">USE_SUPABASE_STORAGE=1</code> and apply migrations.</p>
                      ) : thesisLoading ? (
                        <p className="type-body-sm text-oxford/30">Loading…</p>
                      ) : thesisLoadError ? (
                        <p className="type-body-sm text-escalation/60">{thesisLoadError}</p>
                      ) : (
                        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 items-start">

                          {/* Active thesis */}
                          <div className="flex flex-col gap-5">
                            {thesisSummary ? (
                              <>
                                <p className="type-body-sm text-oxford/40">
                                  v{thesisSummary.active_version_number} · {(thesisSummary.mode ?? 'rule_based') === 'embedding' ? 'AI-enhanced' : 'Rule-based'}
                                </p>
                                <div className="overflow-y-auto max-h-48 p-3 type-meta text-oxford/50 whitespace-pre-wrap break-words font-mono leading-relaxed bg-oxford/[0.03]">
                                  {JSON.stringify(thesisSummary.parsed_json, null, 2)}
                                </div>

                                {thesisSummary.embedding?.status === 'pending' && agentsStatus?.openai_configured && (
                                  <button type="button" disabled={thesisBusy} onClick={() => { void (async () => { setThesisBusy(true); try { await postFundThesisVersion((thesisSummary.raw_text || '').trim()); reloadThesis(); const s = await fetchAgentsStatus(); setAgentsStatus(s ?? null); } catch (e) { setThesisLoadError(e instanceof Error ? e.message : 'Failed'); } finally { setThesisBusy(false); } })(); }} className={`self-start ${outlineBtnCls}`}>
                                    {thesisBusy ? 'Working…' : 'Enable AI alignment'}
                                  </button>
                                )}

                                {thesisSummary.versions.length > 0 && (
                                  <div className="flex flex-col gap-3">
                                    <p className={labelCls}>Version history</p>
                                    <div className="flex items-center gap-3">
                                      <select value={thesisActivateId} onChange={(e) => setThesisActivateId(e.target.value)} className={`${selectCls} flex-1`} style={selectStyle} aria-label="Select version">
                                        {thesisSummary.versions.map((v) => <option key={v.id} value={v.id}>v{v.version_number}{v.is_active ? ' (active)' : ''}</option>)}
                                      </select>
                                      <button type="button" disabled={thesisBusy || !thesisActivateId || !!thesisSummary.versions.find((v) => v.id === thesisActivateId)?.is_active} onClick={() => { void (async () => { setThesisBusy(true); try { await patchFundThesisActiveVersion(thesisActivateId); reloadThesis(); const s = await fetchAgentsStatus(); setAgentsStatus(s ?? null); } catch (e) { setThesisLoadError(e instanceof Error ? e.message : 'Failed'); } finally { setThesisBusy(false); } })(); }} className={outlineBtnCls}>
                                        Set active
                                      </button>
                                    </div>
                                  </div>
                                )}

                                <div className="flex flex-col gap-3">
                                  <p className={labelCls}>Apply to existing pipeline</p>
                                  {thesisReprocessToast && <p className="type-body-sm text-oxford/40" role="status">{thesisReprocessToast}</p>}
                                  <button type="button" disabled={thesisBusy || thesisReprocessRunning} onClick={() => { setThesisReprocessOpen(true); setThesisReprocessModalError(null); setThesisReprocessEligible(null); setThesisReprocessDryLoading(true); void postFundThesisReprocessMissing({ dryRun: true }).then((r) => { if ('eligible' in r) setThesisReprocessEligible(r.eligible); }).catch((e: unknown) => setThesisReprocessModalError(e instanceof Error ? e.message : 'Failed')).finally(() => setThesisReprocessDryLoading(false)); }} className={`self-start ${outlineBtnCls}`}>
                                    Reprocess startups
                                  </button>
                                </div>
                              </>
                            ) : (
                              <p className="type-body-sm text-oxford/40">No mandate yet. Publish one using the editor.</p>
                            )}
                          </div>

                          {/* Publish editor */}
                          <div className="flex flex-col gap-4">
                            <p className={labelCls}>Publish new version</p>
                            <textarea value={thesisDraft} onChange={(e) => setThesisDraft(e.target.value)} rows={14}
                              className="w-full resize-y bg-oxford/[0.03] p-4 type-body-sm text-oxford/80 outline-none placeholder:text-oxford/20"
                              placeholder="Sectors, stage, geography, check size, exclusions, risk posture…" />
                            <button type="button" disabled={thesisBusy || !thesisDraft.trim()} onClick={() => { void (async () => { setThesisBusy(true); try { await postFundThesisVersion(thesisDraft.trim()); reloadThesis(); const s = await fetchAgentsStatus(); setAgentsStatus(s ?? null); } catch (e) { setThesisLoadError(e instanceof Error ? e.message : 'Publish failed'); } finally { setThesisBusy(false); } })(); }} className={`self-start ${outlineBtnCls}`}>
                              {thesisBusy ? 'Publishing…' : 'Publish'}
                            </button>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* ── Pipeline ── */}
                {activeTab === 'pipeline' && (
                  <div className="flex flex-col gap-12 max-w-xl">
                    {agentsStatus && !agentsStatus.agents_will_run && (
                      <p className="type-body-sm text-oxford/40">
                        Pipeline may not run · Worker: {agentsStatus.worker_ready ? 'ready' : 'not ready'} · Supabase: {agentsStatus.supabase_configured ? 'ok' : 'missing'} · OpenAI: {agentsStatus.openai_configured ? 'ok' : 'missing'}
                      </p>
                    )}

                    <div className="flex flex-col gap-4">
                      <p className={labelCls}>Stages</p>
                      <ToggleRow id="scouts_enabled" checked={settings.agent_config.scouts_enabled} onChange={(v) => setAgent('scouts_enabled', v)} label="Scouts" hint="Discover new companies matching your mandate" />
                      <ToggleRow id="reviewers_enabled" checked={settings.agent_config.reviewers_enabled} onChange={(v) => setAgent('reviewers_enabled', v)} label="Reviewers" hint="Score across market, product, team, defensibility" />
                      <ToggleRow id="partners_enabled" checked={settings.agent_config.partners_enabled} onChange={(v) => setAgent('partners_enabled', v)} label="Partners" hint="INVEST / MONITOR / PASS with written rationale" />
                    </div>

                    <div className="flex flex-col gap-6">
                      <p className={labelCls}>Run settings</p>
                      <TextField id="max_agents" label="Companies per cycle" type="number" value={settings.agent_config.max_agents_per_run} onChange={(v) => setAgent('max_agents_per_run', Number(v))} min={1} />
                      <div className="flex flex-col gap-1">
                        <label htmlFor="confidence_threshold" className={labelCls}>Decision threshold</label>
                        <span className={hintCls}>Minimum confidence for an automated call (0–1)</span>
                        <input id="confidence_threshold" type="text"
                          value={typeof settings.agent_config.confidence_threshold === 'number' ? String(settings.agent_config.confidence_threshold) : settings.agent_config.confidence_threshold}
                          onChange={(e) => { const v = e.target.value; const n = Number(v); setAgent('confidence_threshold', v.trim() === '' ? 0.5 : Number.isFinite(n) ? n : v); }}
                          className={inputCls} />
                      </div>
                    </div>

                    {settings.meta_agent && (
                      <div className="flex flex-col gap-6">
                        <p className={labelCls}>Self-optimisation</p>
                        <ToggleRow id="meta_enabled" checked={settings.meta_agent.enabled} onChange={(v) => setSettings((s) => s ? { ...s, meta_agent: { ...(s.meta_agent ?? settings.meta_agent!), enabled: v } } : s)} label="Enable self-optimisation" hint="Reweights scouts and adjusts thresholds over time" />
                        <TextField id="meta_interval" label="Interval (seconds)" hint="86400 = daily" type="number" value={settings.meta_agent.interval_seconds} onChange={(v) => setSettings((s) => s ? { ...s, meta_agent: { ...(s.meta_agent ?? settings.meta_agent!), interval_seconds: Number(v) } } : s)} min={0} />
                        <TextField id="meta_min_reviews" label="Min reviews before tuning" type="number" value={settings.meta_agent.min_reviews} onChange={(v) => setSettings((s) => s ? { ...s, meta_agent: { ...(s.meta_agent ?? settings.meta_agent!), min_reviews: Number(v) } } : s)} min={0} />
                        <TextField id="meta_min_decisions" label="Min decisions before tuning" type="number" value={settings.meta_agent.min_decisions} onChange={(v) => setSettings((s) => s ? { ...s, meta_agent: { ...(s.meta_agent ?? settings.meta_agent!), min_decisions: Number(v) } } : s)} min={0} />
                        <TextField id="meta_cooldown" label="Cooldown (cycles)" type="number" value={settings.meta_agent.mutation_cooldown_cycles} onChange={(v) => setSettings((s) => s ? { ...s, meta_agent: { ...(s.meta_agent ?? settings.meta_agent!), mutation_cooldown_cycles: Number(v) } } : s)} min={0} />
                      </div>
                    )}
                  </div>
                )}

                {/* ── Discovery ── */}
                {activeTab === 'discovery' && (
                  <div className="flex flex-col gap-12 max-w-xl">
                    <div className="flex flex-col gap-6">
                      <p className={labelCls}>Search scope</p>
                      <SelectField id="scout_region" label="Target region" value={settings.agent_config.scout_region} onChange={(v) => setAgent('scout_region', v)}>
                        <option value="europe">Europe</option>
                        <option value="global">Global</option>
                      </SelectField>
                      <ToggleRow id="scout_serp_enabled" checked={settings.agent_config.scout_serp_enabled} onChange={(v) => setAgent('scout_serp_enabled', v)} label="Live web search" hint="Scouts use live searches to surface recently founded companies" />
                      <TextField id="scout_serp_budget" label="Daily searches" hint="Max search queries per day" type="number" value={settings.agent_config.scout_serp_daily_budget} onChange={(v) => setAgent('scout_serp_daily_budget', Number(v))} min={0} />
                    </div>
                  </div>
                )}

                {/* ── Portfolio ── */}
                {activeTab === 'portfolio' && (
                  <div className="flex flex-col gap-12 max-w-xl">
                    <div className="flex flex-col gap-4">
                      <p className={labelCls}>Watchlist</p>
                      <ToggleRow id="auto_watchlist" checked={settings.portfolio.auto_watchlist} onChange={(v) => setPortfolio('auto_watchlist', v)} label="Auto-add high-signal companies" hint="Added when scoring above the signal threshold" />
                    </div>
                    <div className="flex flex-col gap-6">
                      <p className={labelCls}>Monitoring</p>
                      <SelectField id="signal_scan" label="Signal scan frequency" value={settings.portfolio.signal_scan_frequency} onChange={(v) => setPortfolio('signal_scan_frequency', v)}>
                        <option value="hourly">Hourly</option>
                        <option value="every_6h">Every 6 hours</option>
                        <option value="daily">Daily</option>
                      </SelectField>
                      <SelectField id="memo_verbosity" label="Memo depth" value={settings.portfolio.memo_verbosity} onChange={(v) => setPortfolio('memo_verbosity', v)}>
                        <option value="minimal">Brief</option>
                        <option value="standard">Standard</option>
                        <option value="full">Full</option>
                      </SelectField>
                    </div>
                  </div>
                )}

                {/* ── Budget ── */}
                {activeTab === 'budget' && (
                  <div className="flex flex-col gap-12 max-w-xl">
                    <div className="flex flex-col gap-6">
                      <p className={labelCls}>Spending controls</p>
                      <ToggleRow id="cost_budget_enabled" checked={settings.cost_budget?.enabled ?? false} onChange={(v) => setCost('enabled', v)} label="Enable spending limits" hint="Pipeline pauses when a cap is hit" />
                      <TextField id="daily_ceiling" label="Daily cap (USD)" type="number" value={settings.cost_budget.daily_cost_ceiling} onChange={(v) => setCost('daily_cost_ceiling', Number(v))} min={0} step={0.01} />
                      <TextField id="weekly_ceiling" label="Weekly cap (USD)" type="number" value={settings.cost_budget.weekly_cost_ceiling} onChange={(v) => setCost('weekly_cost_ceiling', Number(v))} min={0} step={0.01} />
                      <TextField id="max_tokens" label="Token budget per cycle" hint="Max AI tokens in a single run" type="number" value={settings.cost_budget.max_tokens_per_run} onChange={(v) => setCost('max_tokens_per_run', Number(v))} min={0} />
                      <TextField id="cooldown" label="Cooldown (seconds)" hint="Pause after hitting a cap" type="number" value={settings.cost_budget.cooldown_seconds} onChange={(v) => setCost('cooldown_seconds', Number(v))} min={0} />
                    </div>

                    <div className="flex flex-col gap-6">
                      <p className={labelCls}>Usage today</p>
                      {(settings.system_health?.budget_status?.length ?? 0) > 0 ? (
                        <div className="flex flex-col gap-8">
                          {settings.system_health!.budget_status.map((b: AgentBudgetStatus) => {
                            const callsPct  = b.daily_calls_limit  > 0 ? b.daily_calls_used  / b.daily_calls_limit  : 0;
                            const tokensPct = b.daily_tokens_limit > 0 ? b.daily_tokens_used / b.daily_tokens_limit : 0;
                            return (
                              <div key={b.agent_id} className="flex flex-col gap-3">
                                <p className="type-meta uppercase tracking-[0.12em] text-oxford/50 truncate">{b.agent_id}</p>
                                <div className="flex flex-col gap-1">
                                  <p className="type-meta text-oxford/30">Calls {b.daily_calls_used} / {b.daily_calls_limit}</p>
                                  <div className="h-px w-full bg-oxford/10"><div className="h-full bg-oxford/35" style={{ width: `${Math.min(100, callsPct * 100)}%` }} /></div>
                                </div>
                                <div className="flex flex-col gap-1">
                                  <p className="type-meta text-oxford/30">Tokens {b.daily_tokens_used} / {b.daily_tokens_limit}</p>
                                  <div className="h-px w-full bg-oxford/10"><div className="h-full bg-oxford/35" style={{ width: `${Math.min(100, tokensPct * 100)}%` }} /></div>
                                </div>
                                {b.in_cooldown && <p className="type-meta text-oxford/30">Cooldown until {b.cooldown_until ?? '—'}</p>}
                              </div>
                            );
                          })}
                        </div>
                      ) : (
                        <p className="type-body-sm text-oxford/30">No usage recorded yet.</p>
                      )}
                    </div>
                  </div>
                )}

                {/* ── Account ── */}
                {activeTab === 'account' && (
                  <div className="flex flex-col gap-12">
                    <div className="flex flex-col gap-4">
                      <p className={labelCls}>Profile & security</p>
                      <div className="aethria-clerk-profile min-h-[320px]">
                        <UserProfile appearance={userProfileAppearance} routing="hash" />
                      </div>
                    </div>
                    {userId && (
                      <div className="flex flex-col gap-4">
                        <p className={labelCls}>User ID</p>
                        <p className="type-body-sm text-oxford/40">Set <code className="bg-oxford/[0.05] px-1">AETHRIA_AGENT_USER_ID</code> to this value to run agents locally.</p>
                        <div className="flex items-center gap-3 flex-wrap">
                          <code className="type-meta text-oxford/55 bg-oxford/[0.05] px-3 py-1 select-none" aria-hidden>{userId.replace(/./g, '•')}</code>
                          <button type="button" onClick={() => navigator.clipboard?.writeText(userId).then(() => { setUserIdCopied(true); setTimeout(() => setUserIdCopied(false), 2000); })} className={btnCls}>
                            {userIdCopied ? 'Copied' : 'Copy'}
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                )}

              </motion.div>
            </AnimatePresence>
          </div>
        </div>

      {/* Reprocess modal */}
      {thesisReprocessOpen && (
        <div className="fixed inset-0 z-[220] flex items-center justify-center bg-oxford/25 px-4" role="presentation" onClick={() => { if (!thesisReprocessRunning) setThesisReprocessOpen(false); }}>
          <div role="dialog" aria-modal="true" aria-labelledby="reprocess-title" className="max-w-sm w-full bg-paper p-8" onClick={(e) => e.stopPropagation()}>
            <p id="reprocess-title" className={`${labelCls} mb-5`}>Reprocess startups?</p>
            <p className="type-body-sm text-oxford/50 mb-6 leading-relaxed">Re-runs analysis on startups evaluated before your current mandate. May take a few minutes.</p>
            {thesisReprocessDryLoading
              ? <p className="type-body-sm text-oxford/30 mb-5">Counting eligible startups…</p>
              : thesisReprocessModalError
                ? <p className="type-body-sm text-escalation/60 mb-5">{thesisReprocessModalError}</p>
                : thesisReprocessEligible !== null
                  ? <div className="mb-5 flex flex-col gap-1">
                      <p className="type-body-sm text-oxford/50">{thesisReprocessEligible} startup{thesisReprocessEligible === 1 ? '' : 's'} will be updated.</p>
                      {thesisReprocessEligible > 500 && <p className="type-body-sm text-oxford/30">Large batch — first 1000 per run.</p>}
                      {!agentsStatus?.openai_configured && thesisReprocessEligible >= 1 && <p className="type-body-sm text-oxford/30">Configure <code className="bg-oxford/[0.05] px-1">OPENAI_API_KEY</code> to continue.</p>}
                    </div>
                  : null
            }
            <div className="flex gap-4 justify-end">
              <button type="button" disabled={thesisReprocessRunning} onClick={() => setThesisReprocessOpen(false)} className={btnCls}>Cancel</button>
              <button type="button"
                disabled={thesisReprocessRunning || thesisReprocessDryLoading || thesisReprocessEligible === null || thesisReprocessEligible < 1 || !!thesisReprocessModalError || !agentsStatus?.openai_configured}
                className={`${outlineBtnCls} inline-flex items-center gap-2`}
                onClick={() => { void (async () => { setThesisReprocessRunning(true); setThesisReprocessModalError(null); try { const r = await postFundThesisReprocessMissing(); if (!('processed' in r)) return; setThesisReprocessOpen(false); setThesisReprocessToast(`Reprocessed ${r.processed} startup${r.processed === 1 ? '' : 's'}${r.failed > 0 ? ` (${r.failed} failed)` : ''}`); } catch (e: unknown) { setThesisReprocessModalError(e instanceof Error ? e.message : 'Reprocess failed'); } finally { setThesisReprocessRunning(false); } })(); }}>
                {thesisReprocessRunning
                  ? <><svg className="animate-spin h-3.5 w-3.5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" aria-hidden><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" /><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" /></svg>Reprocessing…</>
                  : 'Continue'
                }
              </button>
            </div>
          </div>
        </div>
      )}

      <AgentLogoutModal
        open={showLogoutModal}
        agentsEnabled={agentsEnabled}
        onCancel={() => setShowLogoutModal(false)}
        onKeepRunning={() => { setShowLogoutModal(false); doLogout(); }}
        onTurnOffAndLogout={handleTurnOffAndLogout}
        onTurnOnAndStay={handleTurnOnAndStay}
      />
    </div>
  );
}
