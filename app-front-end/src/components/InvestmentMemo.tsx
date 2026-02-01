import { useRef } from 'react';
import { motion } from 'framer-motion';
import type { Startup } from '../types/startup';
import { tokens } from '../design-system/tokens';
import {
  getScoreBand,
  QUALITY_LABELS,
  DECISION_LABELS,
  SCORE_DIMENSIONS,
} from '../design-system/semantics';
import { useFocusTrap } from '../hooks';

interface InvestmentMemoProps {
  startup: Startup | null;
  onClose: () => void;
}

function buildJudgmentSummary(startup: Startup): string {
  const r = startup.review;
  const p = startup.partner;
  if (!p) return '';
  const decisionLabel = DECISION_LABELS[p.decision] ?? p.decision;
  const quality = r?.verdict ? QUALITY_LABELS[r.verdict] ?? r.verdict : '';
  const rationale = p.rationale ?? '';
  if (rationale) return `${decisionLabel}. ${rationale}`;
  return `${decisionLabel}. Quality: ${quality}.`;
}

function buildScoreJustification(startup: Startup): string | null {
  const r = startup.review;
  if (!r) return null;
  const scores: number[] = [];
  if (r.market_score != null) scores.push(r.market_score);
  if (r.product_score != null) scores.push(r.product_score);
  if (r.technical_score != null) scores.push(r.technical_score);
  if (r.execution_score != null) scores.push(r.execution_score);
  if (scores.length === 0) return null;
  const avg = scores.reduce((a, b) => a + b, 0) / scores.length;
  const hasLow = scores.some((s) => s <= 5);
  const hasHigh = scores.some((s) => s >= 7);
  if (hasLow && hasHigh)
    return `Scores reflect mixed strength; execution and defensibility concerns offset market potential.`;
  if (hasLow) return `Scores reflect moderate opportunity offset by high execution risk and unproven defensibility.`;
  if (hasHigh) return `Scores support investment-grade opportunity across key dimensions.`;
  return `Average ${avg.toFixed(1)}/10. Scores reflect promising but incomplete validation.`;
}

export default function InvestmentMemo({ startup, onClose }: InvestmentMemoProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  useFocusTrap(true, containerRef);

  if (!startup) return null;

  const hasReview = startup.review != null;
  const hasPartner = startup.partner != null;
  const judgmentSummary = hasPartner ? buildJudgmentSummary(startup) : null;
  const scoreJustification = hasReview ? buildScoreJustification(startup) : null;

  const primaryRisks = startup.review?.diligence_red_flags ?? [];
  const secondaryRisks = (startup.review?.key_risks ?? []).filter(
    (r) => !primaryRisks.some((p) => r.includes(p) || p.includes(r))
  );

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: tokens.motion.duration.medium, ease: tokens.motion.ease }}
      className="fixed inset-0 z-[100] bg-ivory flex items-center justify-center"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-labelledby="memo-title"
    >
      <div
        ref={containerRef}
        className="relative z-10 w-full max-w-4xl max-h-[85vh] sm:max-h-[90vh] flex flex-col mx-4 sm:mx-6 px-4 xs:px-6 lg:px-10 py-6 sm:py-8"
        onClick={(e) => e.stopPropagation()}
      >
        <p className="font-sans text-[10px] uppercase tracking-[0.14em] text-charcoal/45 mb-1">
          Investment memo
        </p>
        <h1
          id="memo-title"
          className="font-sans font-medium text-lg lg:text-xl text-charcoal tracking-tight mb-1"
        >
          {startup.scout.name}
        </h1>
        <p className="font-sans text-[11px] uppercase tracking-[0.12em] text-charcoal/50 mb-6">
          {startup.scout.sector || '—'}
        </p>

        <div className="flex-1 min-h-0 overflow-y-auto no-scrollbar">
          {judgmentSummary && (
            <section className="mb-6 p-4 border border-oxford/15 bg-ivory">
              <h2 className="font-sans text-[11px] uppercase tracking-[0.12em] text-charcoal/60 mb-2">
                Investment judgment
              </h2>
              <p className="font-sans text-[13px] text-charcoal leading-relaxed">
                {judgmentSummary}
              </p>
            </section>
          )}

          <section className="mb-6">
            <h2 className="font-sans text-[11px] uppercase tracking-[0.12em] text-charcoal/60 mb-3">
              Overview
            </h2>
            <div className="space-y-4">
              {startup.scout.problem && (
                <div>
                  <p className="font-sans text-[11px] uppercase tracking-[0.1em] text-charcoal/50 mb-1">Problem</p>
                  <p className="font-sans text-[13px] text-charcoal/80 leading-relaxed">{startup.scout.problem}</p>
                </div>
              )}
              {startup.scout.solution && (
                <div>
                  <p className="font-sans text-[11px] uppercase tracking-[0.1em] text-charcoal/50 mb-1">Solution</p>
                  <p className="font-sans text-[13px] text-charcoal/80 leading-relaxed">{startup.scout.solution}</p>
                </div>
              )}
              {startup.scout.target_users && (
                <div>
                  <p className="font-sans text-[11px] uppercase tracking-[0.1em] text-charcoal/50 mb-1">Target</p>
                  <p className="font-sans text-[13px] text-charcoal/80 leading-relaxed">{startup.scout.target_users}</p>
                </div>
              )}
              {startup.scout.why_now && (
                <div>
                  <p className="font-sans text-[11px] uppercase tracking-[0.1em] text-charcoal/50 mb-1">Why now</p>
                  <p className="font-sans text-[13px] text-charcoal/80 leading-relaxed">{startup.scout.why_now}</p>
                </div>
              )}
            </div>
          </section>

          {hasReview && (
            <section className="mb-6 pt-6 border-t border-oxford/[0.06]">
              <h2 className="font-sans text-[11px] uppercase tracking-[0.12em] text-charcoal/60 mb-3">
                Primary drivers
              </h2>
              <div className="space-y-3">
                {SCORE_DIMENSIONS.slice(0, 2).map(({ id, name }) => {
                  const score = startup.review?.[id as keyof typeof startup.review];
                  if (score == null || typeof score !== 'number') return null;
                  const band = getScoreBand(score);
                  const reasoning = startup.review?.score_reasoning?.[id];
                  return (
                    <div key={id} className="flex flex-col sm:flex-row sm:items-baseline gap-1 sm:gap-4">
                      <div className="sm:w-32 shrink-0">
                        <span className="font-sans text-[13px] text-charcoal/80">{name} </span>
                        <span className="font-sans text-[13px] text-charcoal/70 tabular-nums">{score}/10</span>
                        <span className="font-sans text-[11px] text-charcoal/50 ml-1">({band.label})</span>
                      </div>
                      {reasoning && (
                        <p className="font-sans text-[13px] text-charcoal/80 leading-relaxed">{reasoning}</p>
                      )}
                    </div>
                  );
                })}
              </div>
            </section>
          )}

          {hasReview && (
            <section className="mb-6 pt-6 border-t border-oxford/[0.06]">
              <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1 mb-3">
                <h2 className="font-sans text-[11px] uppercase tracking-[0.12em] text-charcoal/60">
                  Supporting analysis
                </h2>
                <p className="font-sans text-[10px] text-charcoal/40">
                  1–3: Weak · 4–5: Concerning · 6–7: Promising · 8–10: Strong
                </p>
              </div>
              <div className="space-y-4">
                <div className="flex flex-wrap gap-x-6 gap-y-1 font-sans text-[13px]">
                  {SCORE_DIMENSIONS.slice(2).map(({ id, name }) => {
                    const score = startup.review?.[id as keyof typeof startup.review];
                    if (score == null || typeof score !== 'number') return null;
                    const band = getScoreBand(score);
                    return (
                      <span key={id}>
                        <span className="text-charcoal/80">{name}</span>{' '}
                        <span className="text-charcoal/70 tabular-nums">{score}/10</span>
                        <span className="text-charcoal/50 text-[11px] ml-0.5">({band.label})</span>
                      </span>
                    );
                  })}
                </div>
                {scoreJustification && (
                  <p className="font-sans text-[12px] text-charcoal/70 leading-relaxed italic">
                    {scoreJustification}
                  </p>
                )}
                {startup.review?.score_reasoning &&
                  Object.keys(startup.review.score_reasoning).length > 0 && (
                    <div className="space-y-2 pt-2">
                      {SCORE_DIMENSIONS.slice(2).map(({ id, name }) => {
                        const text = startup.review?.score_reasoning?.[id];
                        if (!text) return null;
                        return (
                          <div key={id}>
                            <p className="font-sans text-[11px] uppercase tracking-[0.1em] text-charcoal/50 mb-0.5">
                              {name}
                            </p>
                            <p className="font-sans text-[13px] text-charcoal/80 leading-relaxed">{text}</p>
                          </div>
                        );
                      })}
                    </div>
                  )}
              </div>
            </section>
          )}

          {(primaryRisks.length > 0 || secondaryRisks.length > 0) && (
            <section className="mb-6 pt-6 border-t border-oxford/[0.06]">
              <h2 className="font-sans text-[11px] uppercase tracking-[0.12em] text-charcoal/60 mb-3">
                Risks
              </h2>
              <div className="space-y-4">
                {primaryRisks.length > 0 && (
                  <div>
                    <p className="font-sans text-[11px] uppercase tracking-[0.1em] text-charcoal/50 mb-2">
                      Primary
                    </p>
                    <ul className="space-y-1 font-sans text-[13px] text-charcoal/80 leading-relaxed">
                      {primaryRisks.map((r, i) => (
                        <li key={i} className="flex gap-2">
                          <span className="text-charcoal/40">·</span>
                          <span>{r}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                {secondaryRisks.length > 0 && (
                  <div>
                    <p className="font-sans text-[11px] uppercase tracking-[0.1em] text-charcoal/50 mb-2">
                      Secondary
                    </p>
                    <ul className="space-y-1 font-sans text-[13px] text-charcoal/80 leading-relaxed">
                      {secondaryRisks.map((r, i) => (
                        <li key={i} className="flex gap-2">
                          <span className="text-charcoal/40">·</span>
                          <span>{r}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            </section>
          )}

          {startup.review?.overall_summary && (
            <section className="mb-6 pt-6 border-t border-oxford/[0.06]">
              <h2 className="font-sans text-[11px] uppercase tracking-[0.12em] text-charcoal/60 mb-3">
                Summary
              </h2>
              <p className="font-sans text-[13px] text-charcoal/80 leading-relaxed">
                {startup.review.overall_summary}
              </p>
            </section>
          )}

          {hasPartner && (
            <section className="pt-6 border-t border-oxford/[0.06]">
              <h2 className="font-sans text-[11px] uppercase tracking-[0.12em] text-charcoal/60 mb-3">
                Decision
              </h2>
              <div className="pl-4 border-l-2 border-oxford/20 space-y-2">
                {hasReview && startup.review?.verdict && (
                  <p className="font-sans text-[11px] text-charcoal/50">
                    <span className="uppercase tracking-wide">Quality assessment</span> ·{' '}
                    {startup.review.verdict} ({QUALITY_LABELS[startup.review.verdict] ?? startup.review.verdict})
                  </p>
                )}
                <p className="font-sans text-[11px] text-charcoal/60">
                  <span className="uppercase tracking-wide">Investment decision</span> ·{' '}
                  {startup.partner!.decision} ({DECISION_LABELS[startup.partner!.decision] ?? startup.partner!.decision})
                </p>
                {startup.timestamps?.partnered_at && (
                  <p className="font-sans text-[10px] tabular-nums text-charcoal/40">
                    {new Date(startup.timestamps.partnered_at).toLocaleString('en-GB', {
                      hour12: false,
                      day: '2-digit',
                      month: '2-digit',
                      year: 'numeric',
                      hour: '2-digit',
                      minute: '2-digit',
                      second: '2-digit',
                    })}
                  </p>
                )}
                {startup.partner!.rationale && (
                  <p className="font-sans text-[13px] text-charcoal/75 leading-relaxed pt-1">
                    {startup.partner!.rationale}
                  </p>
                )}
                {startup.partner!.next_action && (
                  <p className="font-sans text-[12px] text-charcoal/55 pt-1">
                    <span className="uppercase tracking-wide">Next</span> · {startup.partner!.next_action}
                  </p>
                )}
              </div>
            </section>
          )}
        </div>

        <div className="flex-none pt-6 mt-4 border-t border-oxford/[0.06]">
          <button
            type="button"
            onClick={onClose}
            className="min-h-[44px] px-4 font-sans text-[11px] uppercase tracking-[0.12em] text-charcoal/50 hover:text-charcoal active:opacity-80 transition-colors duration-300"
          >
            Close
          </button>
        </div>
      </div>
    </motion.div>
  );
}
