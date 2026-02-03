import { useState, useEffect } from 'react';
import { fetchSettings } from '../api/settings';
import type { AgentConfig } from '../api/settings';

interface SystemBarProps {
  scoutCount?: number;
  /** Override nav link (e.g. { href: '/', label: 'Home' } on Settings page) */
  navLink?: { href: string; label: string };
  /** Optional: pass agent config from parent (e.g. SettingsPage). If omitted, fetches from API. */
  agentConfig?: AgentConfig | null;
}

function getStatus(ac: AgentConfig | null): string {
  if (!ac) return 'Active';
  const { scouts_enabled, reviewers_enabled, partners_enabled } = ac;
  const anyOn = scouts_enabled || reviewers_enabled || partners_enabled;
  if (!anyOn) return 'Agents off';
  return 'Active';
}

function getProcessMessage(ac: AgentConfig | null): string {
  if (!ac) return 'System active';
  const { scouts_enabled, reviewers_enabled, partners_enabled } = ac;
  const anyOn = scouts_enabled || reviewers_enabled || partners_enabled;
  if (!anyOn) return 'Agents disabled in settings';
  if (partners_enabled && (reviewers_enabled || scouts_enabled))
    return 'Capital allocation active';
  if (reviewers_enabled && scouts_enabled) return 'Evaluating inbound intelligence';
  if (reviewers_enabled) return 'Evaluating pipeline';
  if (scouts_enabled) return 'Scanning for opportunities';
  if (partners_enabled) return 'Partner layer active';
  return 'System active';
}

/**
 * Instrumentation: status, scout count, process signal. Full-width. Restrained.
 * Status reflects agent config (scouts/reviewers/partners enabled).
 */
export default function SystemBar({
  scoutCount = 0,
  navLink,
  agentConfig: agentConfigProp,
}: SystemBarProps) {
  const link = navLink ?? { href: '/settings', label: 'Settings' };
  const [agentConfig, setAgentConfig] = useState<AgentConfig | null>(
    agentConfigProp ?? null
  );

  useEffect(() => {
    if (agentConfigProp != null) {
      setAgentConfig(agentConfigProp);
      return;
    }
    let cancelled = false;
    const load = () =>
      fetchSettings()
        .then((s) => {
          if (!cancelled) setAgentConfig(s.agent_config);
        })
        .catch(() => {
          if (!cancelled) setAgentConfig(null);
        });
    load();
    const t = setInterval(load, 15_000);
    return () => {
      cancelled = true;
      clearInterval(t);
    };
  }, [agentConfigProp]);

  const status = getStatus(agentConfig);
  const processMessage = getProcessMessage(agentConfig);

  return (
    <div className="fixed top-[3.25rem] left-0 right-0 z-50 border-b border-ivory/[0.12] bg-oxford">
      <div className="w-full min-w-0 px-4 xs:px-6 sm:px-8 lg:px-12 py-2 sm:py-2.5 flex flex-wrap items-center justify-between gap-x-4 sm:gap-x-8 gap-y-2">
        <div className="flex items-center gap-3 sm:gap-6 min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-sans text-[10px] uppercase tracking-[0.14em] text-ivory/60">
              Status
            </span>
            <span className="font-sans text-[12px] text-ivory">{status}</span>
          </div>
          <span className="w-px h-3.5 bg-ivory/25" aria-hidden />
          <div className="flex items-center gap-2">
            <span className="font-sans text-[10px] uppercase tracking-[0.14em] text-ivory/60">
              Scouts
            </span>
            <span className="font-sans text-[12px] tabular-nums text-ivory">
              {scoutCount}
            </span>
          </div>
        </div>
        <div className="flex items-center gap-3 sm:gap-6 min-w-0 flex-1 xs:flex-initial justify-end">
          <div className="min-w-0 overflow-hidden max-w-[50vw] sm:max-w-none">
            <span className="block font-sans text-[11px] text-ivory/70 truncate">
              {processMessage}
            </span>
          </div>
          <span className="w-px h-3.5 bg-ivory/25 shrink-0" aria-hidden />
          <a
            href={link.href}
            className="font-sans text-[11px] uppercase tracking-[0.12em] text-ivory/70 hover:text-ivory transition-colors duration-300 shrink-0"
          >
            {link.label}
          </a>
        </div>
      </div>
    </div>
  );
}
