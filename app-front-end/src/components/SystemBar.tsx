import { useState, useEffect } from 'react';
import { checkHealth } from '../api/health';

interface SystemBarProps {
  scoutCount?: number;
  agentConfig?: unknown;
}

const HEALTH_POLL_MS = 15_000;

/**
 * Status strip: wordmark, agents-online indicator, and time. Settings / Log out live in the footer.
 */
export default function SystemBar(_props: SystemBarProps) {
  const [time, setTime] = useState(new Date());
  const [agentsOnline, setAgentsOnline] = useState<boolean | null>(null);

  useEffect(() => {
    const t = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    const poll = () => {
      checkHealth().then(setAgentsOnline);
    };
    poll();
    const id = setInterval(poll, HEALTH_POLL_MS);
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
          title={agentsOnline === true ? 'Agents online' : agentsOnline === false ? 'Agents offline' : 'Checking…'}
          aria-label={agentsOnline === true ? 'Agents online' : agentsOnline === false ? 'Agents offline' : 'Checking status'}
        >
          <span
            className={`inline-block h-2 w-2 rounded-full shrink-0 transition-colors ${
              agentsOnline === true
                ? 'bg-emerald-400 shadow-[0_0_6px_rgba(52,211,153,0.6)]'
                : agentsOnline === false
                  ? 'bg-ivory/30'
                  : 'bg-amber-400/80 animate-pulse'
            }`}
          />
          <span className="hidden sm:inline">
            {agentsOnline === true ? 'Agents' : agentsOnline === false ? 'Offline' : '…'}
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
