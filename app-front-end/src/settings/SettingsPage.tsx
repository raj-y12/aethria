import { useState, useEffect } from 'react';
import SystemBar from '../components/SystemBar';
import AppFooter from '../components/AppFooter';
import GhostTransition from '../components/GhostTransition';
import {
  fetchSettings,
  patchSettings,
  type Settings,
} from '../api/settings';
import { tokens } from '../design-system/tokens';

export default function SettingsPage() {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [validationErrors, setValidationErrors] = useState<string[]>([]);
  const [saveSuccess, setSaveSuccess] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetchSettings()
      .then((data) => {
        if (!cancelled) setSettings(data);
      })
      .catch(() => {
        if (!cancelled) setSettings(null);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const handleSave = async () => {
    if (!settings) return;
    setSaving(true);
    setValidationErrors([]);
    setSaveSuccess(false);
    const result = await patchSettings(settings);
    setSaving(false);
    if (result.error) {
      setValidationErrors(result.error.errors);
      return;
    }
    setSaveSuccess(true);
    if (result.data) setSettings(result.data);
  };

  const updateCostBudget = <K extends keyof Settings['cost_budget']>(
    key: K,
    value: Settings['cost_budget'][K]
  ) => {
    setSettings((s) =>
      s ? { ...s, cost_budget: { ...s.cost_budget, [key]: value } } : s
    );
  };

  const updateAgentConfig = <K extends keyof Settings['agent_config']>(
    key: K,
    value: Settings['agent_config'][K]
  ) => {
    setSettings((s) =>
      s ? { ...s, agent_config: { ...s.agent_config, [key]: value } } : s
    );
  };

  const updatePortfolio = <K extends keyof Settings['portfolio']>(
    key: K,
    value: Settings['portfolio'][K]
  ) => {
    setSettings((s) =>
      s ? { ...s, portfolio: { ...s.portfolio, [key]: value } } : s
    );
  };

  if (loading) {
    return (
      <div className="h-screen w-full flex flex-col overflow-hidden bg-paper">
        <SystemBar scoutCount={0} />
        <main className="flex-1 min-h-0 pt-24 flex items-center justify-center">
          <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-oxford/60">
            Loading settings…
          </p>
        </main>
        <AppFooter navLink={{ href: '/', label: 'Home' }} />
      </div>
    );
  }

  if (!settings) {
    return (
      <div className="h-screen w-full flex flex-col overflow-hidden bg-paper">
        <SystemBar scoutCount={0} />
        <main className="flex-1 min-h-0 pt-24 flex items-center justify-center">
          <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-oxford/60">
            Failed to load settings.
          </p>
        </main>
        <AppFooter navLink={{ href: '/', label: 'Home' }} />
      </div>
    );
  }

  const inputCls =
    'w-full min-w-0 sm:max-w-[12rem] border-0 border-b border-oxford/[0.15] bg-transparent font-sans text-[14px] text-oxford placeholder:text-oxford/40 outline-none py-2 focus:border-oxford transition-colors duration-150 rounded-none';
  const labelCls = 'block font-mono text-[10px] uppercase tracking-[0.22em] text-oxford/60 mb-1.5';

  const Toggle = ({
    id,
    checked,
    onChange,
    label,
  }: {
    id: string;
    checked: boolean;
    onChange: (v: boolean) => void;
    label: string;
  }) => (
    <div className="flex items-center justify-between gap-4 py-1">
      <label htmlFor={id} className="font-sans text-[14px] text-oxford">
        {label}
      </label>
      <button
        id={id}
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={`relative inline-flex h-5 w-10 shrink-0 cursor-pointer items-center rounded-full transition-colors duration-300 focus-visible:ring-1 focus-visible:ring-oxford/40 focus-visible:ring-offset-2 focus-visible:ring-offset-paper ${
          checked
            ? 'bg-oxford'
            : 'bg-transparent border border-oxford/[0.2] hover:border-oxford/30'
        }`}
        style={{ transitionTimingFunction: tokens.motion.easeCss }}
      >
        <span
          className={`pointer-events-none block h-4 w-4 rounded-full shadow-sm transition-transform duration-300 ${
            checked ? 'translate-x-5 bg-ivory' : 'translate-x-0.5 bg-oxford/50'
          }`}
          style={{ transitionTimingFunction: tokens.motion.easeCss }}
          aria-hidden
        />
      </button>
    </div>
  );

  return (
    <div className="h-screen w-full flex flex-col overflow-hidden bg-paper">
      <SystemBar scoutCount={0} agentConfig={settings.agent_config} />

      <main className="flex-1 min-h-0 pt-24 overflow-y-auto">
        <div className="w-full max-w-[1800px] mx-auto px-6 sm:px-8 lg:px-12 py-8 lg:py-10 pb-16">
          <GhostTransition>
            <div className="pb-6 border-b border-oxford/[0.06]">
              <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-oxford/60">
                Control plane
              </p>
              <h1 className="font-sans font-semibold text-[28px] text-oxford tracking-tight mt-1" style={{ letterSpacing: '-0.02em' }}>
                Settings
              </h1>
            </div>

            {validationErrors.length > 0 && (
              <div className="mt-6 pb-6 border-b border-oxford/[0.06]">
                <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-alert-crimson mb-2">
                  Validation errors
                </p>
                <ul className="font-sans text-[13px] text-alert-crimson space-y-1">
                  {validationErrors.map((e, i) => (
                    <li key={i}>{e}</li>
                  ))}
                </ul>
              </div>
            )}

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-8 sm:gap-10 lg:gap-12 pt-8 lg:pt-10">
            <section className="space-y-5">
              <h2 className="font-mono text-[10px] uppercase tracking-[0.22em] text-oxford/60 mb-4">
                Cost & budget controls
              </h2>
              {[
                {
                  id: 'max_tokens',
                  label: 'Max tokens per run',
                  value: settings.cost_budget.max_tokens_per_run,
                  onChange: (v: number) =>
                    updateCostBudget('max_tokens_per_run', Math.max(0, v)),
                  type: 'number' as const,
                  min: 0,
                },
                {
                  id: 'daily_ceiling',
                  label: 'Daily cost ceiling',
                  value: settings.cost_budget.daily_cost_ceiling,
                  onChange: (v: number) =>
                    updateCostBudget('daily_cost_ceiling', Math.max(0, v)),
                  type: 'number' as const,
                  min: 0,
                  step: 0.01,
                },
                {
                  id: 'weekly_ceiling',
                  label: 'Weekly cost ceiling',
                  value: settings.cost_budget.weekly_cost_ceiling,
                  onChange: (v: number) =>
                    updateCostBudget('weekly_cost_ceiling', Math.max(0, v)),
                  type: 'number' as const,
                  min: 0,
                  step: 0.01,
                },
                {
                  id: 'cooldown',
                  label: 'Cooldown between runs (seconds)',
                  value: settings.cost_budget.cooldown_seconds,
                  onChange: (v: number) =>
                    updateCostBudget('cooldown_seconds', Math.max(0, v)),
                  type: 'number' as const,
                  min: 0,
                },
              ].map((f) => (
                <div key={f.id}>
                  <label htmlFor={f.id} className={labelCls}>
                    {f.label}
                  </label>
                  <input
                    id={f.id}
                    type={f.type}
                    min={f.min}
                    step={f.step}
                    value={f.value}
                    onChange={(e) => f.onChange(Number(e.target.value) || 0)}
                    className={inputCls}
                  />
                </div>
              ))}
            </section>

            <section className="space-y-5">
              <h2 className="font-mono text-[10px] uppercase tracking-[0.22em] text-oxford/60 mb-4">
                Agent configuration
              </h2>
              {[
                {
                  id: 'scouts_enabled',
                  label: 'Scouts enabled',
                  checked: settings.agent_config.scouts_enabled,
                  onChange: (v: boolean) =>
                    updateAgentConfig('scouts_enabled', v),
                },
                {
                  id: 'reviewers_enabled',
                  label: 'Reviewers enabled',
                  checked: settings.agent_config.reviewers_enabled,
                  onChange: (v: boolean) =>
                    updateAgentConfig('reviewers_enabled', v),
                },
                {
                  id: 'partners_enabled',
                  label: 'Partners enabled',
                  checked: settings.agent_config.partners_enabled,
                  onChange: (v: boolean) =>
                    updateAgentConfig('partners_enabled', v),
                },
              ].map((c) => (
                <Toggle
                  key={c.id}
                  id={c.id}
                  checked={c.checked}
                  onChange={c.onChange}
                  label={c.label}
                />
              ))}
              <div>
                <label htmlFor="max_agents" className={labelCls}>
                  Max agents per run
                </label>
                <input
                  id="max_agents"
                  type="number"
                  min={1}
                  value={settings.agent_config.max_agents_per_run}
                  onChange={(e) =>
                    updateAgentConfig(
                      'max_agents_per_run',
                      Math.max(1, Number(e.target.value) || 1)
                    )
                  }
                  className={inputCls}
                />
              </div>
              <div>
                <label htmlFor="confidence_threshold" className={labelCls}>
                  Confidence threshold (0–1 or bucketed label)
                </label>
                <input
                  id="confidence_threshold"
                  type="text"
                  value={
                    typeof settings.agent_config.confidence_threshold === 'number'
                      ? String(settings.agent_config.confidence_threshold)
                      : settings.agent_config.confidence_threshold
                  }
                  onChange={(e) => {
                    const v = e.target.value;
                    const num = Number(v);
                    updateAgentConfig(
                      'confidence_threshold',
                      v.trim() === '' ? 0.5 : Number.isFinite(num) ? num : v
                    );
                  }}
                  className={inputCls}
                />
              </div>
            </section>

            <section className="space-y-5">
              <h2 className="font-mono text-[10px] uppercase tracking-[0.22em] text-oxford/60 mb-4">
                Portfolio behaviour
              </h2>
              <Toggle
                id="auto_watchlist"
                checked={settings.portfolio.auto_watchlist}
                onChange={(v) => updatePortfolio('auto_watchlist', v)}
                label="Auto-watchlist"
              />
              <div>
                <label htmlFor="signal_scan" className={labelCls}>
                  Signal scan frequency (low-frequency only)
                </label>
                <select
                  id="signal_scan"
                  value={settings.portfolio.signal_scan_frequency}
                  onChange={(e) =>
                    updatePortfolio('signal_scan_frequency', e.target.value)
                  }
                  className={inputCls}
                >
                  <option value="hourly">Hourly</option>
                  <option value="every_6h">Every 6 hours</option>
                  <option value="daily">Daily</option>
                </select>
              </div>
              <div>
                <label htmlFor="memo_verbosity" className={labelCls}>
                  Memo verbosity level
                </label>
                <select
                  id="memo_verbosity"
                  value={settings.portfolio.memo_verbosity}
                  onChange={(e) =>
                    updatePortfolio('memo_verbosity', e.target.value)
                  }
                  className={inputCls}
                >
                  <option value="minimal">Minimal</option>
                  <option value="standard">Standard</option>
                  <option value="full">Full</option>
                </select>
              </div>
            </section>
          </div>

            <div className="pt-10 border-t border-oxford/[0.06] mt-10">
              <button
                type="button"
                onClick={handleSave}
                disabled={saving}
                className="inline-flex items-center justify-center py-3 px-5 font-mono text-[10px] uppercase tracking-[0.2em] text-ivory bg-oxford rounded-none transition-opacity duration-200 disabled:opacity-50 disabled:cursor-not-allowed hover:opacity-90"
              >
                {saving ? 'Saving…' : 'Save settings'}
              </button>
              {saveSuccess && (
                <p className="mt-3 font-mono text-[10px] uppercase tracking-[0.22em] text-oxford/60" role="status" aria-live="polite">
                  Settings saved.
                </p>
              )}
            </div>
          </GhostTransition>
        </div>
      </main>

      <AppFooter navLink={{ href: '/', label: 'Home' }} />
    </div>
  );
}
