import { useState, useEffect } from 'react';

interface CommandDockProps {
  scoutCount: number;
}

export default function CommandDock({ scoutCount }: CommandDockProps) {
  const [currentTime, setCurrentTime] = useState(new Date());
  const [systemStatus, setSystemStatus] = useState<'Active' | 'Scanning'>('Active');

  useEffect(() => {
    const timer = setInterval(() => {
      setCurrentTime(new Date());
    }, 1000);

    // Simulate system status changes
    const statusTimer = setInterval(() => {
      setSystemStatus(prev => prev === 'Active' ? 'Scanning' : 'Active');
    }, 5000);

    return () => {
      clearInterval(timer);
      clearInterval(statusTimer);
    };
  }, []);

  const formatTime = (date: Date) => {
    return date.toLocaleTimeString('en-US', {
      hour12: false,
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  };

  return (
    <nav className="fixed top-6 lg:top-8 left-1/2 -translate-x-1/2 z-50 w-[95%] lg:w-[90%] max-w-6xl">
      <div className="backdrop-blur-xl bg-oxford/40 border border-silver/60 text-heritage px-6 lg:px-8 py-3 lg:py-4 flex flex-col lg:flex-row items-start lg:items-center justify-between gap-4 lg:gap-0">
        <div className="flex flex-col lg:flex-row items-start lg:items-center gap-4 lg:gap-8">
          <div className="flex items-center gap-3">
            <span className="text-heritage/80 font-body text-[11px] uppercase tracking-[0.18em]">
              System Status
            </span>
            <div className="flex items-center gap-2">
              <div
                className={`w-2 h-2 rounded-full ${
                  systemStatus === 'Active' ? 'bg-gold' : 'bg-alert-crimson'
                }`}
              />
              <span className="text-heritage font-body text-[11px] font-medium">
                {systemStatus}
              </span>
            </div>
          </div>

          <div className="h-6 w-px bg-silver/60" />

          <div className="flex items-center gap-3">
            <span className="text-heritage/80 font-body text-[11px] uppercase tracking-[0.18em]">
              Scout Count
            </span>
            <span className="text-heritage font-display text-base font-bold">
              {scoutCount}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <span className="text-heritage/80 font-body text-[11px] uppercase tracking-[0.18em]">
            Global Clock
          </span>
          <span className="text-heritage font-display text-sm font-bold tabular-nums">
            {formatTime(currentTime)}
          </span>
        </div>
      </div>
    </nav>
  );
}
