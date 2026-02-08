import { useState, useEffect } from 'react';
import type { AgentConfig } from '../api/settings';

interface LedgerHeaderProps {
  navLink?: { href: string; label: string };
  agentConfig?: AgentConfig | null;
}

function agentsActive(cfg: AgentConfig | null | undefined): boolean {
  if (!cfg) return false;
  return cfg.scouts_enabled || cfg.reviewers_enabled || cfg.partners_enabled;
}

/** Nav/Status: 9px Sans, uppercase, tracking-[0.4em], opacity-40 — extreme corners */
const wingCls = 'font-sans text-[9px] uppercase tracking-[0.4em] text-midnight-blue/40 hover:text-midnight-blue/60 transition-opacity tabular-nums';

/**
 * Aethria Sovereign — Logo absolute center. Nav/Status at extreme corners.
 */
export default function LedgerHeader({ navLink, agentConfig: agentConfigProp }: LedgerHeaderProps) {
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

  return (
    <header className="fixed top-0 left-0 right-0 z-50 flex items-center justify-between px-4 xs:px-6 sm:px-8 pt-6 pb-6">
      {/* Left: extreme corner */}
      <div className="flex flex-col gap-0.5 shrink-0">
        <span className={wingCls}>System {active ? 'Active' : 'Idle'}</span>
        <span className={wingCls}>Local {formatted}</span>
      </div>

      {/* Center: Aethria (Libre Baskerville) */}
      <a
        href="/"
        className="absolute left-1/2 -translate-x-1/2 font-display font-medium text-midnight-blue text-[11px] sm:text-[12px] tracking-[0.2em] hover:opacity-80 transition-opacity"
        aria-label="Aethria"
      >
        Aethria
      </a>

      {/* Right: extreme corner */}
      <div className="flex items-center gap-8 shrink-0">
        {navLink && (
          <a href={navLink.href} className={wingCls}>
            {navLink.label}
          </a>
        )}
        <button
          type="button"
          onClick={() => {
            localStorage.removeItem('aethria_last_activity');
            window.location.href = '/';
          }}
          className={`${wingCls} text-left`}
        >
          Log out
        </button>
      </div>
    </header>
  );
}
