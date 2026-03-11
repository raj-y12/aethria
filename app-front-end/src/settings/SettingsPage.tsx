import { useState, useEffect, useLayoutEffect, useRef } from 'react';
import SystemBar from '../components/SystemBar';
import AppFooter from '../components/AppFooter';
import GhostTransition from '../components/GhostTransition';
import { fetchSettings, patchSettings, type Settings } from '../api/settings';
import { tokens } from '../design-system/tokens';

type TabId = 'cost' | 'agent' | 'portfolio';

const inputCls =
  'w-full min-w-0 max-w-[11rem] border-0 border-b bg-transparent font-sans text-[14px] text-oxford placeholder:text-oxford/40 py-2 outline-none rounded-none transition-colors duration-150';
const inputBorder = 'border-oxford/[0.08] focus:border-oxford';
const labelCls = 'block font-mono text-[11px] uppercase tracking-[0.16em] text-oxford/60 mb-2';
const selectCls = inputCls + ' border-oxford/[0.08] focus:border-oxford cursor-pointer appearance-none pr-8 max-w-full';
const toggleLabelCls = 'font-sans text-[14px] text-oxford';
const groupHeadingCls = 'font-mono text-[11px] uppercase tracking-[0.16em] text-oxford/50 mb-3';

const TOGGLE_TRACK = 'h-6 w-11 shrink-0 rounded-full border cursor-pointer inline-flex items-center';
const TOGGLE_KNOB = 'h-4 w-4 rounded-full shadow-sm pointer-events-none block';

function Toggle({
  id,
  checked,
  onChange,
  label,
}: { id: string; checked: boolean; onChange: (v: boolean) => void; label: string }) {
  return (
    <div className="flex items-center justify-between gap-4 py-2 min-h-[2.75rem]">
      <label htmlFor={id} className={toggleLabelCls}>{label}</label>
      <button
        id={id}
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={`relative ${TOGGLE_TRACK} transition-colors duration-300 focus-visible:ring-1 focus-visible:ring-oxford/30 focus-visible:ring-offset-2 focus-visible:ring-offset-paper ${
          checked ? 'bg-oxford border border-oxford' : 'bg-oxford/30 border-0'
        }`}
        style={{ transitionTimingFunction: tokens.motion.easeCss }}
      >
        <span
          className={`${TOGGLE_KNOB} ${checked ? 'translate-x-5 bg-ivory' : 'translate-x-1 bg-oxford/50'}`}
          style={{
            transition: `transform ${tokens.motion.duration.short}s ${tokens.motion.easeCss}, background-color 0.2s ${tokens.motion.easeCss}`,
          }}
          aria-hidden
        />
      </button>
    </div>
  );
}

function Field({
  id,
  label,
  value,
  onChange,
  type = 'number',
  min,
  step,
}: {
  id: string;
  label: string;
  value: number | string;
  onChange: (v: number | string) => void;
  type?: 'number' | 'text';
  min?: number;
  step?: number;
}) {
  return (
    <div className="py-1">
      <label htmlFor={id} className={labelCls}>{label}</label>
      <input
        id={id}
        type={type}
        min={min}
        step={step}
        value={value}
        onChange={(e) => (type === 'number' ? onChange(Number(e.target.value) || 0) : onChange(e.target.value))}
        className={`${inputCls} ${inputBorder}`}
      />
    </div>
  );
}

export default function SettingsPage() {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [validationErrors, setValidationErrors] = useState<string[]>([]);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [activeTab, setActiveTab] = useState<TabId>('cost');
  const [underline, setUnderline] = useState({ left: 0, width: 0 });
  const navRef = useRef<HTMLDivElement>(null);
  const tabRefs = useRef<(HTMLButtonElement | null)[]>([]);

  const tabs: { id: TabId; label: string }[] = [
    { id: 'cost', label: 'Cost & budget' },
    { id: 'agent', label: 'Agent configuration' },
    { id: 'portfolio', label: 'Portfolio behaviour' },
  ];

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

  useLayoutEffect(() => {
    const nav = navRef.current;
    const index = tabs.findIndex((t) => t.id === activeTab);
    const tab = tabRefs.current[index];
    if (nav && tab) {
      setUnderline({ left: tab.offsetLeft, width: tab.offsetWidth });
    }
  }, [activeTab]);

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

  if (loading) {
    return (
      <div className="h-screen w-full flex flex-col overflow-hidden bg-paper">
        <SystemBar scoutCount={0} />
        <main className="flex-1 min-h-0 pt-24 flex items-center justify-center">
          <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-oxford/60">Loading settings…</p>
        </main>
        <AppFooter navLink={{ href: '/', label: 'Home' }} />
      </div>
    );
  }
  if (!settings) {
    return (
      <div className="h-screen w-full flex flex-col overflow-hidden bg-paper">
        <SystemBar scoutCount={0} />
        <main className="flex-1 min-h-0 pt-24 flex flex-col items-center justify-center gap-3 px-6">
          <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-oxford/60">Failed to load settings.</p>
          {loadError && (
            <p className="font-mono text-[10px] text-oxford/70 max-w-md text-center">
              {loadError}
            </p>
          )}
          <p className="font-mono text-[10px] text-oxford/50 max-w-md text-center">
            Set VITE_API_URL in the app build to your backend URL. On Render, set ALLOWED_ORIGINS to this app’s URL (e.g. https://your-app.vercel.app).
          </p>
        </main>
        <AppFooter navLink={{ href: '/', label: 'Home' }} />
      </div>
    );
  }

  return (
    <div className="h-screen w-full flex flex-col overflow-hidden bg-paper">
      <SystemBar scoutCount={0} agentConfig={settings.agent_config} />
      <main className="flex-1 min-h-0 pt-24 flex flex-col">
        <div className="flex-1 min-h-0 flex flex-col max-w-[1800px] mx-auto w-full px-6 sm:px-8 lg:px-12">
          <GhostTransition className="flex flex-col flex-1 min-h-0">
            <header className="flex-none pt-2 pb-6 border-b border-oxford/[0.06]">
              <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-oxford/60">Control plane</p>
              <h1 className="font-sans font-semibold text-2xl text-oxford tracking-tight mt-1" style={{ letterSpacing: '-0.02em' }}>Settings</h1>
            </header>
            {validationErrors.length > 0 && (
              <div className="flex-none py-4 border-b border-oxford/[0.06]">
                <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-oxford/70 mb-2">Validation errors</p>
                <ul className="font-sans text-[14px] text-oxford/80 space-y-1">
                  {validationErrors.map((e, i) => <li key={i}>{e}</li>)}
                </ul>
              </div>
            )}
            <nav ref={navRef} className="flex-none flex relative border-b border-oxford/[0.06]" aria-label="Settings categories">
              {tabs.map(({ id, label }, i) => (
                <button
                  key={id}
                  ref={(el) => { tabRefs.current[i] = el; }}
                  type="button"
                  onClick={() => setActiveTab(id)}
                  className={`px-4 py-3 font-mono text-[11px] uppercase tracking-[0.16em] transition-colors duration-200 ${
                    activeTab === id ? 'text-oxford' : 'text-oxford/50 hover:text-oxford/70'
                  }`}
                  style={{ transitionTimingFunction: tokens.motion.easeCss }}
                >
                  {label}
                </button>
              ))}
              <span
                className="absolute bottom-0 left-0 h-0.5 bg-oxford"
                style={{
                  width: underline.width,
                  transform: `translateX(${underline.left}px)`,
                  transition: `transform ${tokens.motion.duration.short}s ${tokens.motion.easeCss}, width ${tokens.motion.duration.short}s ${tokens.motion.easeCss}`,
                }}
                aria-hidden
              />
            </nav>
            <div className="flex-1 min-h-0 py-6 space-y-8">
              {activeTab === 'cost' && (
                <>
                  <section>
                    <h3 className={groupHeadingCls}>Limits</h3>
                    <div className="grid grid-cols-2 lg:grid-cols-3 gap-x-10 gap-y-1">
                      <Field id="max_tokens" label="Max tokens per run" value={settings.cost_budget.max_tokens_per_run} onChange={(v) => setCost('max_tokens_per_run', Number(v))} min={0} />
                      <Field id="daily_ceiling" label="Daily cost ceiling" value={settings.cost_budget.daily_cost_ceiling} onChange={(v) => setCost('daily_cost_ceiling', Number(v))} min={0} step={0.01} />
                      <Field id="weekly_ceiling" label="Weekly cost ceiling" value={settings.cost_budget.weekly_cost_ceiling} onChange={(v) => setCost('weekly_cost_ceiling', Number(v))} min={0} step={0.01} />
                    </div>
                  </section>
                  <section>
                    <h3 className={groupHeadingCls}>Throttle</h3>
                    <div className="grid grid-cols-2 lg:grid-cols-3 gap-x-10 gap-y-1">
                      <Field id="cooldown" label="Cooldown (seconds)" value={settings.cost_budget.cooldown_seconds} onChange={(v) => setCost('cooldown_seconds', Number(v))} min={0} />
                    </div>
                  </section>
                </>
              )}
              {activeTab === 'agent' && (
                <>
                  <section>
                    <h3 className={groupHeadingCls}>Pipeline</h3>
                    <div className="grid grid-cols-2 lg:grid-cols-3 gap-x-10 gap-y-1">
                      <Toggle id="scouts_enabled" checked={settings.agent_config.scouts_enabled} onChange={(v) => setAgent('scouts_enabled', v)} label="Scouts enabled" />
                      <Toggle id="reviewers_enabled" checked={settings.agent_config.reviewers_enabled} onChange={(v) => setAgent('reviewers_enabled', v)} label="Reviewers enabled" />
                      <Toggle id="partners_enabled" checked={settings.agent_config.partners_enabled} onChange={(v) => setAgent('partners_enabled', v)} label="Partners enabled" />
                    </div>
                  </section>
                  <section>
                    <h3 className={groupHeadingCls}>Scouting</h3>
                    <div className="grid grid-cols-2 lg:grid-cols-3 gap-x-10 gap-y-1">
                      <div className="py-1">
                        <label htmlFor="scout_region" className={labelCls}>Scout region</label>
                        <select id="scout_region" value={settings.agent_config.scout_region} onChange={(e) => setAgent('scout_region', e.target.value)} className={selectCls}>
                          <option value="europe">Europe</option>
                          <option value="global">Global</option>
                        </select>
                      </div>
                      <Toggle id="scout_serp_enabled" checked={settings.agent_config.scout_serp_enabled} onChange={(v) => setAgent('scout_serp_enabled', v)} label="SERP scouting" />
                      <Field id="scout_serp_budget" label="SERP daily budget" value={settings.agent_config.scout_serp_daily_budget} onChange={(v) => setAgent('scout_serp_daily_budget', Number(v))} min={0} />
                    </div>
                  </section>
                  <section>
                    <h3 className={groupHeadingCls}>Run</h3>
                    <div className="grid grid-cols-2 lg:grid-cols-3 gap-x-10 gap-y-1">
                      <Field id="max_agents" label="Max agents per run" value={settings.agent_config.max_agents_per_run} onChange={(v) => setAgent('max_agents_per_run', Number(v))} min={1} />
                      <div className="py-1">
                        <label htmlFor="confidence_threshold" className={labelCls}>Confidence threshold</label>
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
                        />
                      </div>
                    </div>
                  </section>
                </>
              )}
              {activeTab === 'portfolio' && (
                <>
                  <section>
                    <h3 className={groupHeadingCls}>Watchlist</h3>
                    <div className="grid grid-cols-2 lg:grid-cols-3 gap-x-10 gap-y-1">
                      <Toggle id="auto_watchlist" checked={settings.portfolio.auto_watchlist} onChange={(v) => setPortfolio('auto_watchlist', v)} label="Auto-watchlist" />
                    </div>
                  </section>
                  <section>
                    <h3 className={groupHeadingCls}>Frequency & output</h3>
                    <div className="grid grid-cols-2 lg:grid-cols-3 gap-x-10 gap-y-1">
                      <div className="py-1">
                        <label htmlFor="signal_scan" className={labelCls}>Signal scan</label>
                        <select id="signal_scan" value={settings.portfolio.signal_scan_frequency} onChange={(e) => setPortfolio('signal_scan_frequency', e.target.value)} className={selectCls}>
                          <option value="hourly">Hourly</option>
                          <option value="every_6h">Every 6h</option>
                          <option value="daily">Daily</option>
                        </select>
                      </div>
                      <div className="py-1">
                        <label htmlFor="memo_verbosity" className={labelCls}>Memo verbosity</label>
                        <select id="memo_verbosity" value={settings.portfolio.memo_verbosity} onChange={(e) => setPortfolio('memo_verbosity', e.target.value)} className={selectCls}>
                          <option value="minimal">Minimal</option>
                          <option value="standard">Standard</option>
                          <option value="full">Full</option>
                        </select>
                      </div>
                    </div>
                  </section>
                </>
              )}
            </div>
            <footer className="flex-none pt-5 pb-2 border-t border-oxford/[0.06] flex items-center justify-between gap-4">
              <button
                type="button"
                onClick={handleSave}
                disabled={saving}
                className="min-h-[44px] py-2.5 px-5 font-mono text-[11px] uppercase tracking-[0.16em] text-ivory bg-oxford rounded-none disabled:opacity-50 disabled:cursor-not-allowed hover:opacity-90 transition-opacity duration-200"
              >
                {saving ? 'Saving…' : 'Save settings'}
              </button>
              {saveSuccess && (
                <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-oxford/50" role="status" aria-live="polite">
                  Settings saved.
                </p>
              )}
            </footer>
          </GhostTransition>
        </div>
      </main>
      <AppFooter navLink={{ href: '/', label: 'Home' }} />
    </div>
  );
}
