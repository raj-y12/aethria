import { motion } from 'framer-motion';
import type { Startup } from '../types/startup';
import { tokens } from '../design-system/tokens';
import { verdictTextClass } from '../design-system/verdictTint';
import { DECISION_LABELS } from '../design-system/semantics';

interface WorkGridProps {
  startups: Startup[];
  onStartupClick: (startup: Startup) => void;
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
 * Live capital allocation engine. Order: verdicts reached (top) → reviewed, no decision → unreviewed (bottom).
 */
export default function WorkGrid({ startups, onStartupClick }: WorkGridProps) {
  const resolved = startups.filter((s) => s.partner?.decision != null);
  const reviewedNoDecision = startups.filter((s) => s.review != null && !s.partner?.decision);
  const unreviewed = startups.filter((s) => s.review == null);

  const ordered = [...resolved, ...reviewedNoDecision, ...unreviewed];

  const renderRow = (startup: Startup, index: number) => {
    const hasVerdict = !!startup.partner?.decision;
    const verdictTime = startup.timestamps?.partnered_at;

    return (
      <motion.div
        key={startup.id}
        role="button"
        tabIndex={0}
        aria-label={`View ${startup.scout.name}`}
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: tokens.motion.duration.short, delay: index * 0.03, ease: tokens.motion.ease }}
        className="border-b border-oxford/[0.06] cursor-pointer outline-none focus-visible:ring-1 focus-visible:ring-oxford/15 focus-visible:ring-inset transition-colors duration-300 hover:bg-charcoal/[0.02] active:bg-charcoal/[0.03]"
        onClick={() => onStartupClick(startup)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            onStartupClick(startup);
          }
        }}
      >
        <div className="flex flex-col lg:flex-row lg:items-start gap-3 sm:gap-4 py-4 sm:py-5 lg:py-6">
          {/* Main reading flow: entity — stacks on mobile */}
          <div className="flex-1 min-w-0 overflow-hidden">
            <h2 className="font-sans font-medium text-charcoal text-base lg:text-lg tracking-tight">
              {startup.scout.name}
            </h2>
            <p className="font-sans text-[12px] sm:text-[13px] text-charcoal/65 mt-1 leading-relaxed line-clamp-2 break-words">
              {startup.scout.one_line || (
                <span className="text-charcoal/35">—</span>
              )}
            </p>
            <div className="mt-2 font-sans text-[11px] uppercase tracking-[0.08em] text-charcoal/40">
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

          {/* Judgement: log-style, below main on mobile; right-aligned on desktop */}
          {hasVerdict && verdictTime && (
            <div className="shrink-0 lg:w-48 lg:pt-0.5 lg:text-right border-t border-oxford/[0.06] pt-3 lg:border-t-0 lg:pt-0">
              <div className="font-sans text-[11px] text-charcoal/50 tabular-nums tracking-wide">
                {formatVerdictTime(verdictTime)}
              </div>
              <div className="font-sans text-[11px] mt-0.5">
                <span className="text-charcoal/50">Decision </span>
                <span className={verdictTextClass(startup.partner!.decision)}>
                  {DECISION_LABELS[startup.partner!.decision] ?? startup.partner!.decision}
                </span>
                <span className="text-charcoal/40 font-normal"> · system consensus</span>
              </div>
            </div>
          )}
        </div>
      </motion.div>
    );
  };

  if (startups.length === 0) {
    return (
      <div className="w-full py-16 border-b border-oxford/[0.06] flex items-center justify-center">
        <p className="font-sans text-[13px] text-charcoal/40 text-center">
          No evaluations yet. The system is idle.
        </p>
      </div>
    );
  }

  return (
    <div className="w-full">
      {ordered.map((s, i) => renderRow(s, i))}
    </div>
  );
}
