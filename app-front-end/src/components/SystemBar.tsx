import { useState, useEffect } from 'react';
import { fetchSettings } from '../api/settings';

interface SystemBarProps {
  scoutCount?: number;
  agentConfig?: unknown;
}

const AGENT_STATUS_POLL_MS = 15_000;

/** True if at least one agent layer (scouts, reviewers, partners) is enabled in settings. */
function agentsOnFromSettings(ac: { scouts_enabled?: boolean; reviewers_enabled?: boolean; partners_enabled?: boolean } | undefined): boolean {
  if (!ac) return false;
  return !!(ac.scouts_enabled || ac.reviewers_enabled || ac.partners_enabled);
}

/**
 * Status strip: wordmark, agents on/off indicator (from settings), and time. Settings / Log out live in the footer.
 */
export default function SystemBar(_props: SystemBarProps) {
  const [time, setTime] = useState(new Date());
  const [agentsOn, setAgentsOn] = useState<boolean | null>(null);

  useEffect(() => {
    const t = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    const poll = () => {
      fetchSettings()
        .then((s) => setAgentsOn(agentsOnFromSettings(s.agent_config)))
        .catch(() => setAgentsOn(null));
    };
    poll();
    const id = setInterval(poll, AGENT_STATUS_POLL_MS);
    return () => clearInterval(id);
  }, []);

  const formatted = time.toLocaleTimeString('en-GB', {
    hour12: false,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });

  return (
    <header
      className="fixed top-6 left-6 sm:left-8 lg:left-12 right-0 z-50 flex items-center justify-between h-14 px-6 sm:px-8 lg:px-12 bg-oxford border-b border-white/[0.06]"
      style={{ boxShadow: '0 1px 0 0 rgba(255,255,255,0.06)' }}
      aria-label="System"
    >
      <a
        href="/"
        className="font-display font-bold text-[15px] text-ivory hover:opacity-90 transition-opacity tracking-tight"
        aria-label="Aethria"
      >
        Aethria
      </a>

      <div className="flex items-center gap-3">
        <span
          className="flex items-center gap-1.5 font-mono text-[10px] text-ivory/60"
          title={agentsOn === true ? 'Agents on' : agentsOn === false ? 'Agents off' : 'Checking…'}
          aria-label={agentsOn === true ? 'Agents on' : agentsOn === false ? 'Agents off' : 'Checking status'}
        >
          <span
            className={`inline-block h-2 w-2 rounded-full shrink-0 transition-colors ${
              agentsOn === true
                ? 'bg-emerald-400 shadow-[0_0_6px_rgba(52,211,153,0.6)]'
                : agentsOn === false
                  ? 'bg-ivory/30'
                  : 'bg-amber-400/80 animate-pulse'
            }`}
          />
          <span className="hidden sm:inline">
            {agentsOn === true ? 'On' : agentsOn === false ? 'Off' : '…'}
          </span>
        </span>
        <span
          className="font-mono text-[10px] tabular-nums text-ivory/80"
          aria-live="polite"
        >
          {formatted}
        </span>
      </div>
    </header>
  );
}
