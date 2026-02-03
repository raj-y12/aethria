import { useState, useEffect } from 'react';

/**
 * Central temporal reference. Minimal context; no decoration.
 */
export default function GlobalClock() {
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
    <div className="fixed top-0 left-0 right-0 z-50 h-[3.25rem] flex items-center justify-between gap-4 px-4 xs:px-6 sm:px-8 lg:px-12 bg-ivory shrink-0">
      <a
        href="/"
        className="font-display text-[11px] sm:text-[12px] text-oxford/50 hover:text-oxford/70 tracking-tight transition-colors duration-300"
        aria-label="Aethria"
      >
        Aethria
      </a>
      <div className="absolute left-1/2 -translate-x-1/2 flex items-center gap-2 sm:gap-3">
        <span className="font-sans text-[10px] uppercase tracking-[0.2em] text-charcoal/40">
          Local
        </span>
        <span
          className="font-sans text-charcoal text-[12px] sm:text-[13px] tabular-nums tracking-[0.12em]"
          aria-live="polite"
        >
          {formatted}
        </span>
      </div>
      <button
        type="button"
        onClick={() => {
          localStorage.removeItem('aethria_last_activity');
          window.location.href = '/';
        }}
        className="font-sans text-[10px] sm:text-[11px] uppercase tracking-[0.12em] text-charcoal/50 hover:text-charcoal transition-colors duration-300 shrink-0"
      >
        Log out
      </button>
    </div>
  );
}
