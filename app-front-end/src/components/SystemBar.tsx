import { useState, useEffect } from 'react';

interface SystemBarProps {
  scoutCount?: number;
  agentConfig?: unknown;
}

/**
 * Status strip: wordmark and time only. Settings / Log out live in the footer.
 */
export default function SystemBar(_props: SystemBarProps) {
  const [time, setTime] = useState(new Date());

  useEffect(() => {
    const t = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(t);
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

      <span
        className="font-mono text-[10px] tabular-nums text-ivory/80"
        aria-live="polite"
      >
        {formatted}
      </span>
    </header>
  );
}
