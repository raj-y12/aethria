import { useState, useEffect } from 'react';
import type { AgentConfig } from '../api/settings';

interface AppHeaderProps {
  scoutCount: number;
  navLink?: { href: string; label: string };
  agentConfig?: AgentConfig | null;
}

function agentsActive(cfg: AgentConfig | null | undefined): boolean {
  if (!cfg) return false;
  return cfg.scouts_enabled || cfg.reviewers_enabled || cfg.partners_enabled;
}

export default function AppHeader({
  scoutCount: _scoutCount,
  navLink: _navLink,
  agentConfig: agentConfigProp,
}: AppHeaderProps) {
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

  const registryCls = 'font-mono text-[10px] uppercase tracking-[0.2em] text-oxford';

  return (
    <>
      {/* The Anchor: Aethria at top-left, 32px from top, 48px from left */}
      <a
        href="/"
        className="fixed z-[60] font-display font-medium text-[11px] sm:text-[12px] text-oxford tracking-tight border-b-[0.5px] border-oxford pb-0.5 opacity-100 hover:opacity-90 transition-opacity duration-300"
        style={{ top: '32px', left: '48px' }}
        aria-label="Aethria"
      >
        Aethria
      </a>

      {/* Registry Block: top-right, asset-tag style */}
      <div
        className="fixed top-6 right-6 sm:right-8 z-[60] px-3 py-2 rounded-none"
        style={{
          border: '0.5px solid rgba(0, 33, 71, 0.2)',
        }}
      >
        <div className="flex flex-col gap-0.5">
          <span className={registryCls}>STATUS {active ? 'OK' : 'Idle'}</span>
          <span className={`${registryCls} tabular-nums`} aria-live="polite">
            TIME {formatted}
          </span>
          <button
            type="button"
            onClick={() => {
              localStorage.removeItem('aethria_last_activity');
              window.location.href = '/';
            }}
            className={`${registryCls} text-left hover:opacity-70 transition-opacity`}
          >
            LOG OUT
          </button>
        </div>
      </div>
    </>
  );
}
