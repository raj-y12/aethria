/**
 * Fixed bottom-left: SCOUTS count. 10px Mono, 40% opacity Oxford.
 */
export default function MarginStatus({ scoutCount }: { scoutCount: number }) {
  const monoCls = 'font-mono text-[9px] uppercase tracking-[0.2em] text-deep-slate/60';

  return (
    <div
      className="fixed bottom-4 left-4 sm:bottom-6 sm:left-6 z-40 flex items-center gap-2 sm:gap-3"
      aria-label="Margin status"
    >
      <span className={`${monoCls} tabular-nums`}>{scoutCount} Scouts</span>
    </div>
  );
}
