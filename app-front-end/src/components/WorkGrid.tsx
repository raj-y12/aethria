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
    hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit',
  });
}

function isEscalation(s: Startup): boolean {
  return !!(s.partner?.human_review_required && !s.human_resolution);
}

function sortKey(s: Startup): string {
  return s.timestamps?.partnered_at ?? s.timestamps?.reviewed_at ?? s.timestamps?.discovered_at ?? '';
}

export default function WorkGrid({ startups, onStartupClick, selectedId }: WorkGridProps) {
  const escalations = startups.filter(isEscalation).sort((a, b) => sortKey(b).localeCompare(sortKey(a)));
  const decided = startups.filter((s) => s.partner?.decision != null && !isEscalation(s)).sort((a, b) => sortKey(b).localeCompare(sortKey(a)));
  const reviewedNoDecision = startups.filter((s) => s.review != null && !s.partner?.decision).sort((a, b) => sortKey(b).localeCompare(sortKey(a)));
  const unreviewed = startups.filter((s) => s.review == null).sort((a, b) => sortKey(b).localeCompare(sortKey(a)));
  const ordered = [...escalations, ...decided, ...reviewedNoDecision, ...unreviewed];

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
        const isEsc = isEscalation(startup);
        const hasDisagreement = startup.review?.reviewer_disagreement === true;
        const confidence = startup.scout.confidence;

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
            className={`group cursor-pointer outline-none focus-visible:ring-1 focus-visible:ring-oxford/15 focus-visible:ring-inset border-b border-oxford/[0.06]${hasDisagreement ? ' border-l-2 border-l-oxford/40' : ''}`}
            onClick={() => onStartupClick(startup)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onStartupClick(startup); }
            }}
          >
            <div className="flex flex-col lg:flex-row lg:items-start gap-3 sm:gap-4 py-4 sm:py-5 lg:py-6">
              <div className="flex-1 min-w-0 overflow-hidden">
                <div className="flex items-center gap-2">
                  {isSelected && (
                    <motion.span
                      className="w-1.5 h-1.5 shrink-0 rounded-full bg-oxford/40"
                      aria-hidden
                      initial={{ opacity: 0, scale: 0.5 }}
                      animate={{ opacity: 1, scale: 1 }}
                      transition={{ duration: tokens.motion.duration.short, ease: tokens.motion.ease }}
                    />
                  )}
                  {isEsc && !isSelected && (
                    <span className="w-1.5 h-1.5 shrink-0 rounded-full bg-oxford escalation-pulse" aria-hidden />
                  )}
                  <h2 className={`font-sans font-semibold text-oxford text-base lg:text-lg tracking-tight min-w-0${!isSelected ? ' transition-transform duration-300 ease-out group-hover:translate-x-1' : ''}`}>
                    {startup.scout.name}
                  </h2>
                  {hasDisagreement && (
                    <span className="font-mono text-[9px] uppercase tracking-[0.16em] text-oxford/40 shrink-0">contested</span>
                  )}
                </div>
                {/* One-liner: hidden by default, shown on hover/selected */}
                <div
                  className={`overflow-hidden transition-all duration-200 ease-out ${isSelected ? 'max-h-12 opacity-100 mt-1' : 'max-h-0 opacity-0 group-hover:max-h-12 group-hover:opacity-100 group-hover:mt-1'}`}
                >
                  <p className="font-sans text-[13px] sm:text-[14px] text-oxford/70 leading-relaxed line-clamp-2 break-words" style={{ lineHeight: 1.6 }}>
                    {startup.scout.one_line || <span className="text-oxford/40">—</span>}
                  </p>
                </div>
                <div className="mt-2 font-mono text-[11px] uppercase tracking-[0.16em] text-oxford/60 flex items-center gap-3">
                  {startup.scout.sector && (
                    <span>{startup.scout.sector}</span>
                  )}
                  {confidence != null && (
                    <span className="flex items-center gap-1.5">
                      <span className="tabular-nums">{Math.round(confidence * 100)}%</span>
                      <span className="inline-block w-10 h-0.5" style={{ backgroundColor: 'rgba(0,33,71,0.08)' }}>
                        <span className="block h-full" style={{ width: `${Math.round(confidence * 100)}%`, backgroundColor: 'rgba(0,33,71,0.3)' }} />
                      </span>
                    </span>
                  )}
                </div>
              </div>
              {/* Right side: verdict badge or escalation badge */}
              {isEsc ? (
                <div className="shrink-0 lg:w-40 lg:text-right pt-3 lg:pt-0 border-t border-oxford/[0.06] lg:border-t-0 flex flex-col items-start lg:items-end gap-1.5">
                  <span
                    className="inline-flex items-center justify-center py-2 px-3 font-mono text-[10px] uppercase tracking-[0.2em] text-paper rounded-none"
                    style={{ backgroundColor: '#002147' }}
                  >
                    awaiting review
                  </span>
                </div>
              ) : hasVerdict && verdictTime ? (
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
              ) : null}
            </div>
          </motion.div>
        );
      })}
    </div>
  );
}
