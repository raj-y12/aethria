import { useState, useEffect, useCallback } from 'react';
import { motion } from 'framer-motion';
import type { Startup } from '../types/startup';
import { tokens } from '../design-system/tokens';
import DecisionBadge from './DecisionBadge';
import EmptyState from './EmptyState';

const ORIENT_DISMISSED_KEY = 'aethria_dashboard_orient_dismissed';
const COACH_MARK_DURATION_MS = 4000;

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

  const [showCoachMark, setShowCoachMark] = useState(false);
  useEffect(() => {
    if (typeof window === 'undefined' || ordered.length === 0) return;
    try {
      if (!window.localStorage.getItem(ORIENT_DISMISSED_KEY)) setShowCoachMark(true);
    } catch {
      /* ignore */
    }
  }, [ordered.length]);

  useEffect(() => {
    if (!showCoachMark) return;
    const t = window.setTimeout(() => {
      try {
        window.localStorage.setItem(ORIENT_DISMISSED_KEY, '1');
      } catch {
        /* ignore */
      }
      setShowCoachMark(false);
    }, COACH_MARK_DURATION_MS);
    return () => clearTimeout(t);
  }, [showCoachMark]);

  const handleStartupClick = useCallback(
    (startup: Startup) => {
      if (showCoachMark) {
        try {
          window.localStorage.setItem(ORIENT_DISMISSED_KEY, '1');
        } catch {
          /* ignore */
        }
        setShowCoachMark(false);
      }
      onStartupClick(startup);
    },
    [onStartupClick, showCoachMark]
  );

  if (startups.length === 0) {
    return (
      <div className="w-full h-full min-h-[12rem] flex flex-col items-center justify-center border-b border-oxford/[0.06]">
        <EmptyState
          label="Pipeline"
          body="Scouts are running; first deals in a few minutes."
        />
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
            className={`group cursor-pointer outline-none focus-visible:ring-1 focus-visible:ring-oxford/25 focus-visible:ring-inset border-b border-oxford/[0.06] btn-interaction${hasDisagreement ? ' border-l-2 border-l-oxford/40' : ''}`}
            onClick={() => handleStartupClick(startup)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); handleStartupClick(startup); }
            }}
          >
            {/* Single column on mobile/tablet; two columns (60/40) only from lg up */}
            <div className="flex flex-col gap-3 sm:gap-4 py-4 sm:py-5 lg:grid lg:grid-cols-[3fr_2fr] lg:items-start lg:gap-4 lg:py-6">
              <div className="min-w-0 overflow-hidden">
                <div className="flex items-center gap-2">
                  {isSelected && (
                    <motion.span
                      className="w-1.5 h-1.5 shrink-0 rounded-full bg-oxford"
                      aria-hidden
                      initial={{ opacity: 0, scale: 0.5 }}
                      animate={{ opacity: 1, scale: 1 }}
                      transition={{ duration: tokens.motion.duration.short, ease: tokens.motion.ease }}
                    />
                  )}
                  {/* Burgundy: escalation-only — dot indicates human review required */}
                  {isEsc && !isSelected && (
                    <span
                      className="w-1.5 h-1.5 shrink-0 rounded-full escalation-dot-active"
                      style={{ backgroundColor: 'var(--color-accent)' }}
                      aria-hidden
                    />
                  )}
                  <h2
                    className={`type-body font-semibold text-oxford tracking-tight min-w-0${!isSelected ? ' group-hover:translate-x-1' : ''}`}
                    style={!isSelected ? { transition: 'transform var(--motion-short) var(--motion-ease)' } : undefined}
                  >
                    {startup.scout.name}
                  </h2>
                  {hasDisagreement && (
                    <span className="type-label-section text-oxford/40 shrink-0">contested</span>
                  )}
                </div>
                {/* One-liner: hidden by default, shown on hover/selected */}
                <div
                  className={`overflow-hidden transition-all ${isSelected ? 'max-h-12 opacity-100 mt-1' : 'max-h-0 opacity-0 group-hover:max-h-12 group-hover:opacity-100 group-hover:mt-1'}`}
                  style={{ transitionDuration: 'var(--motion-short)', transitionTimingFunction: 'var(--motion-ease)' }}
                >
                  <p className="type-body text-oxford/80 leading-relaxed line-clamp-2 break-words">
                    {startup.scout.one_line || <span className="text-oxford/40">—</span>}
                  </p>
                </div>
                <div className="mt-2 type-label-section text-oxford/60 flex items-center gap-3">
                  {startup.scout.sector && (
                    <span>{startup.scout.sector}</span>
                  )}
                  {confidence != null && (
                    <span className="flex items-center gap-1.5">
                      <span className="tabular-nums">{Math.round(confidence * 100)}%</span>
                      <span className="inline-block w-10 h-0.5 bg-oxford/25">
                        <span className="block h-full bg-oxford/40" style={{ width: `${Math.round(confidence * 100)}%` }} />
                      </span>
                    </span>
                  )}
                </div>
              </div>
              {/* Right side: hover cue + verdict badge (labels below cue so both visible) */}
              <div className="pt-3 border-t border-oxford/[0.06] flex flex-col items-start gap-1.5 min-w-0 lg:pt-0 lg:border-t-0 lg:text-right lg:items-end">
                <span
                  className="type-label-tab text-oxford/40 opacity-0 group-hover:opacity-100 min-h-[1.25rem] flex items-center justify-end w-full"
                  style={{ transition: 'opacity var(--motion-micro) var(--motion-ease)' }}
                  aria-hidden
                >
                  → memo
                </span>
                <div className="flex flex-col items-start gap-1.5 lg:items-end">
                  {isEsc ? (
                    <DecisionBadge variant="awaiting" />
                  ) : hasVerdict && verdictTime ? (
                    <>
                      <span className="type-meta text-oxford/60 tabular-nums">
                        {formatVerdictTime(verdictTime)}
                      </span>
                      <DecisionBadge
                        variant={
                          startup.partner!.decision === 'YES'
                            ? 'YES'
                            : startup.partner!.decision === 'NO' || startup.partner!.decision === 'PASS'
                              ? 'NO'
                              : 'MAYBE'
                        }
                      />
                    </>
                  ) : null}
                </div>
              </div>
            </div>
            {/* First-visit coach mark: single nudge below first card, auto-dismiss or on first click */}
            {index === 0 && showCoachMark && (
              <p
                className="type-label-tab text-oxford/25 mt-1 pb-2"
              >
                Click to open memo
              </p>
            )}
          </motion.div>
        );
      })}
    </div>
  );
}
