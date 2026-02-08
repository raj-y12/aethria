import { useState, useEffect } from 'react';
import type { AgentConfig } from '../api/settings';

interface SystemStatusBarProps {
  scoutCount: number;
  navLink?: { href: string; label: string };
  agentConfig?: AgentConfig | null;
}

function agentsActive(cfg: AgentConfig | null | undefined): boolean {
  if (!cfg) return false;
  return cfg.scouts_enabled || cfg.reviewers_enabled || cfg.partners_enabled;
}

/**
 * Deal Flow Terminal — System Status Bar (32px)
 * [●] SYSTEM ACTIVE | LOCAL time | X SCOUTS DEPLOYED     SETTINGS | LOG OUT
 */
export default function SystemStatusBar({
  scoutCount,
  navLink,
  agentConfig: agentConfigProp,
}: SystemStatusBarProps) {
  const [time, setTime] = useState(new Date());
  const [agentConfig, setAgentConfig] = useState<AgentConfig | null>(null);

  useEffect(() => {
    const t = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    if (agentConfigProp != null) {
      setAgentConfig(agentConfigProp);
      return;
    }
    let cancelled = false;
    const fetchSettings = async () => {
      try {
        const res = await fetch('/api/settings', { headers: { Accept: 'application/json' } });
        if (cancelled || !res.ok) return;
        const data = await res.json();
        if (!cancelled && data?.agent_config) setAgentConfig(data.agent_config);
      } catch {
        /* ignore */
      }
    };
    void fetchSettings();
    const id = setInterval(fetchSettings, 15000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [agentConfigProp]);

  const cfg = agentConfigProp ?? agentConfig;
  const active = agentsActive(cfg);
  const formatted = time.toLocaleTimeString('en-GB', {
    hour12: false,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });

  const barCls = 'font-sans text-[9px] font-medium uppercase tracking-[0.2em] text-oxford/70';

  return (
    <div
      className="fixed top-0 left-0 right-0 z-50 h-8 flex items-center justify-between px-6 sm:px-8 lg:px-12 bg-shadow-cream border-b border-oxford/[0.15]"
      style={{ borderWidth: '0.5px' }}
      aria-label="System status"
    >
      <div className="flex items-center gap-8">
        <span className="flex items-center gap-2">
          <span
            className="w-[3px] h-[3px] rounded-full bg-white/60 shrink-0"
            aria-hidden
          />
          <span className={barCls}>{active ? 'System Active' : 'System Idle'}</span>
        </span>
        <span className={`${barCls} tabular-nums`}>Local {formatted}</span>
        <span className={barCls}>{scoutCount} Scouts Deployed</span>
      </div>
      <div className="flex items-center gap-8">
        {navLink && (
          <a
            href={navLink.href}
            className={`${barCls} hover:underline transition-all duration-200`}
          >
            {navLink.label}
          </a>
        )}
        <button
          type="button"
          onClick={() => {
            localStorage.removeItem('aethria_last_activity');
            window.location.href = '/';
          }}
          className={`${barCls} text-left hover:underline transition-all duration-200`}
        >
          Log out
        </button>
      </div>
    </div>
  );
}
