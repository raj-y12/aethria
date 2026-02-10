import { motion } from 'framer-motion';
import type { Startup } from '../types/startup';
import { tokens } from '../design-system/tokens';
import { DECISION_LABELS } from '../design-system/semantics';

interface WorkGridProps {
  startups: Startup[];
  onStartupClick: (startup: Startup) => void;
  selectedId?: string | null;
}

function formatVerdictTime(iso: string): string {
  return new Date(iso).toLocaleTimeString('en-GB', {
    hour12: false,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

/**
 * Registry list on paper. Oxford text, frame borders.
 */
export default function WorkGrid({ startups, onStartupClick, selectedId }: WorkGridProps) {
  const resolved = startups.filter((s) => s.partner?.decision != null);
  const reviewedNoDecision = startups.filter((s) => s.review != null && !s.partner?.decision);
  const unreviewed = startups.filter((s) => s.review == null);
  const ordered = [...resolved, ...reviewedNoDecision, ...unreviewed];

  if (startups.length === 0) {
    return (
      <div className="w-full py-20 flex flex-col items-center justify-center border-b border-oxford/[0.06]">
        <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-center text-oxford/60">
          No evaluations yet. The system is idle.
        </p>
      </div>
    );
  }

  return (
    <div className="w-full">
      {ordered.map((startup, index) => {
        const hasVerdict = !!startup.partner?.decision;
        const verdictTime = startup.timestamps?.partnered_at;
        const isSelected = selectedId != null && startup.id === selectedId;

        return (
          <motion.div
            key={startup.id}
            role="button"
            tabIndex={0}
            aria-label={`View ${startup.scout.name}`}
            aria-current={isSelected ? 'true' : undefined}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: tokens.motion.duration.short, delay: index * 0.03, ease: tokens.motion.ease }}
            className="group cursor-pointer outline-none focus-visible:ring-1 focus-visible:ring-oxford/15 focus-visible:ring-inset border-b border-oxford/[0.06]"
            onClick={() => onStartupClick(startup)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                onStartupClick(startup);
              }
            }}
          >
            <div className="flex flex-col lg:flex-row lg:items-start gap-3 sm:gap-4 py-4 sm:py-5 lg:py-6">
              <div className="flex-1 min-w-0 overflow-hidden">
                {isSelected ? (
                  <div className="flex items-center gap-2">
                    <motion.span
                      className="w-1.5 h-1.5 shrink-0 rounded-full bg-oxford/40"
                      aria-hidden
                      initial={{ opacity: 0, scale: 0.5 }}
                      animate={{ opacity: 1, scale: 1 }}
                      transition={{ duration: tokens.motion.duration.short, ease: tokens.motion.ease }}
                    />
                    <h2 className="font-sans font-semibold text-oxford text-base lg:text-lg tracking-tight min-w-0">
                      {startup.scout.name}
                    </h2>
                  </div>
                ) : (
                  <h2 className="font-sans font-semibold text-oxford text-base lg:text-lg tracking-tight transition-transform duration-300 ease-out group-hover:translate-x-1">
                    {startup.scout.name}
                  </h2>
                )}
                <p className="font-sans text-[13px] sm:text-[14px] text-oxford/70 mt-1 leading-relaxed line-clamp-2 break-words" style={{ lineHeight: 1.6 }}>
                  {startup.scout.one_line || <span className="text-oxford/40">—</span>}
                </p>
                <div className="mt-2 font-mono text-[11px] uppercase tracking-[0.16em] text-oxford/60">
                  {startup.scout.sector && (
                    <span>
                      {startup.scout.sector}
                      {startup.scout.confidence != null && (
                        <> · {Math.round(startup.scout.confidence * 100)}%</>
                      )}
                    </span>
                  )}
                </div>
              </div>
              {hasVerdict && verdictTime && (
                <div className="shrink-0 lg:w-40 lg:text-right pt-3 lg:pt-0 border-t border-oxford/[0.06] lg:border-t-0 flex flex-col items-start lg:items-end gap-1.5">
                  <span className="font-mono text-[10px] uppercase tracking-[0.22em] text-oxford/50 tabular-nums">
                    {formatVerdictTime(verdictTime)}
                  </span>
                  <span
                    className="inline-flex items-center justify-center py-2 px-3 font-mono text-[10px] uppercase tracking-[0.2em] text-ivory rounded-none"
                    style={{ backgroundColor: '#002147' }}
                  >
                    {DECISION_LABELS[startup.partner!.decision] ?? startup.partner!.decision}
                  </span>
                </div>
              )}
            </div>
          </motion.div>
        );
      })}
    </div>
  );
}
