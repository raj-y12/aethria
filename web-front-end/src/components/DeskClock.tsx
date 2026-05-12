import { useEffect, useState } from 'react';

function formatDesk(d: Date, timeZone: string) {
  return d.toLocaleTimeString('en-GB', {
    timeZone,
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  });
}

export default function DeskClock({ className = '' }: { className?: string }) {
  const [now, setNow] = useState(() => new Date());

  useEffect(() => {
    const tick = () => setNow(new Date());
    tick();
    const id = setInterval(tick, 30_000);
    return () => clearInterval(id);
  }, []);

  const lon = formatDesk(now, 'Europe/London');
  const nyc = formatDesk(now, 'America/New_York');

  return (
    <div
      className={`font-mono text-[11px] tracking-[0.12em] uppercase tabular-nums text-[var(--label-muted)] sm:text-[12px] ${className}`}
      aria-label={`Desk time London ${lon}, New York ${nyc}`}
    >
      <div className="hidden whitespace-nowrap sm:block">
        <span className="text-[rgba(0,27,71,0.55)]">Lon</span> <span>{lon}</span>
        <span className="mx-2 text-[rgba(0,27,71,0.2)]" aria-hidden>
          │
        </span>
        <span className="text-[rgba(0,27,71,0.55)]">Nyc</span> <span>{nyc}</span>
      </div>
      <div className="flex flex-col items-end gap-0.5 leading-tight sm:hidden">
        <span>
          <span className="text-[rgba(0,27,71,0.55)]">Lon</span> {lon}
        </span>
        <span>
          <span className="text-[rgba(0,27,71,0.55)]">Nyc</span> {nyc}
        </span>
      </div>
    </div>
  );
}
