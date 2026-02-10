import type { Startup } from '../types/startup';
import {
  getScoreBand,
  QUALITY_LABELS,
  DECISION_LABELS,
  SCORE_DIMENSIONS,
} from '../design-system/semantics';

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

export interface InvestmentMemoContentProps {
  startup: Startup;
  onClose?: () => void;
  /** When true, used in side panel (no outer padding; panel provides it). */
  embedded?: boolean;
}

/**
 * Memo body only. Used in full-screen modal and in the right-side panel.
 */
export default function InvestmentMemoContent({
  startup,
  onClose,
  embedded = false,
}: InvestmentMemoContentProps) {
  const hasReview = startup.review != null;
  const hasPartner = startup.partner != null;
  const judgmentSummary = hasPartner ? buildJudgmentSummary(startup) : null;
  const scoreJustification = hasReview ? buildScoreJustification(startup) : null;

  const primaryRisks = startup.review?.diligence_red_flags ?? [];
  const secondaryRisks = (startup.review?.key_risks ?? []).filter(
    (r) => !primaryRisks.some((p) => r.includes(p) || p.includes(r))
  );

  const wrapperCls = embedded
    ? 'flex flex-col h-full min-h-0'
    : 'flex flex-col';

  return (
    <div className={wrapperCls}>
      <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-oxford/60 mb-1">
        Investment memo
      </p>
      <h1
        id="memo-title"
        className="font-sans font-semibold text-lg lg:text-xl text-oxford tracking-tight mb-1"
        style={{ letterSpacing: '-0.02em' }}
      >
        {startup.scout.name}
      </h1>
      <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-oxford/60 mb-6">
        {startup.scout.sector || '—'}
      </p>

      <div className={`flex-1 min-h-0 overflow-y-auto no-scrollbar ${embedded ? 'pr-1' : ''}`}>
        {judgmentSummary && (
          <section className="mb-6 p-4 border border-oxford/[0.06] bg-paper">
            <h2 className="font-mono text-[11px] uppercase tracking-[0.16em] text-oxford/60 mb-2">
              Investment judgment
            </h2>
            <p className="font-sans text-[13px] text-oxford leading-relaxed">
              {judgmentSummary}
            </p>
          </section>
        )}

        <section className="mb-6">
          <h2 className="font-mono text-[11px] uppercase tracking-[0.16em] text-oxford/60 mb-3">
            Overview
          </h2>
          <div className="space-y-4">
            {startup.scout.problem && (
              <div>
                <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-oxford/60 mb-1">Problem</p>
                <p className="font-sans text-[13px] text-oxford/80 leading-relaxed">{startup.scout.problem}</p>
              </div>
            )}
            {startup.scout.solution && (
              <div>
                <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-oxford/60 mb-1">Solution</p>
                <p className="font-sans text-[13px] text-oxford/80 leading-relaxed">{startup.scout.solution}</p>
              </div>
            )}
            {startup.scout.target_users && (
              <div>
                <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-oxford/60 mb-1">Target</p>
                <p className="font-sans text-[13px] text-oxford/80 leading-relaxed">{startup.scout.target_users}</p>
              </div>
            )}
            {startup.scout.why_now && (
              <div>
                <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-oxford/60 mb-1">Why now</p>
                <p className="font-sans text-[13px] text-oxford/80 leading-relaxed">{startup.scout.why_now}</p>
              </div>
            )}
          </div>
        </section>

        {hasReview && (
          <section className="mb-6 pt-6 border-t border-oxford/[0.06]">
            <h2 className="font-mono text-[11px] uppercase tracking-[0.16em] text-oxford/60 mb-3">
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
                      <span className="font-sans text-[13px] text-oxford/80">{name} </span>
                      <span className="font-sans text-[13px] text-oxford/70 tabular-nums">{score}/10</span>
                      <span className="font-sans text-[11px] text-oxford/50 ml-1">({band.label})</span>
                    </div>
                    {reasoning && (
                      <p className="font-sans text-[13px] text-oxford/80 leading-relaxed">{reasoning}</p>
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
              <h2 className="font-mono text-[11px] uppercase tracking-[0.16em] text-oxford/60">
                Supporting analysis
              </h2>
              <p className="font-sans text-[10px] text-oxford/40">
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
                      <span className="text-oxford/80">{name}</span>{' '}
                      <span className="text-oxford/70 tabular-nums">{score}/10</span>
                      <span className="text-oxford/50 text-[11px] ml-0.5">({band.label})</span>
                    </span>
                  );
                })}
              </div>
              {scoreJustification && (
                <p className="font-sans text-[12px] text-oxford/70 leading-relaxed italic">
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
                          <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-oxford/60 mb-0.5">
                            {name}
                          </p>
                          <p className="font-sans text-[13px] text-oxford/80 leading-relaxed">{text}</p>
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
            <h2 className="font-mono text-[11px] uppercase tracking-[0.16em] text-oxford/60 mb-3">
              Risks
            </h2>
            <div className="space-y-4">
              {primaryRisks.length > 0 && (
                <div>
                  <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-oxford/60 mb-2">
                    Primary
                  </p>
                  <ul className="space-y-1 font-sans text-[13px] text-oxford/80 leading-relaxed">
                    {primaryRisks.map((r, i) => (
                      <li key={i} className="flex gap-2">
                        <span className="text-oxford/40">·</span>
                        <span>{r}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {secondaryRisks.length > 0 && (
                <div>
                  <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-oxford/60 mb-2">
                    Secondary
                  </p>
                  <ul className="space-y-1 font-sans text-[13px] text-oxford/80 leading-relaxed">
                    {secondaryRisks.map((r, i) => (
                      <li key={i} className="flex gap-2">
                        <span className="text-oxford/40">·</span>
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
            <h2 className="font-mono text-[11px] uppercase tracking-[0.16em] text-oxford/60 mb-3">
              Summary
            </h2>
            <p className="font-sans text-[13px] text-oxford/80 leading-relaxed">
              {startup.review.overall_summary}
            </p>
          </section>
        )}

        {hasPartner && (
          <section className="pt-6 border-t border-oxford/[0.06]">
            <h2 className="font-mono text-[11px] uppercase tracking-[0.16em] text-oxford/60 mb-3">
              Decision
            </h2>
            <div className="pl-4 border-l-2 border-oxford/20 space-y-2">
              {hasReview && startup.review?.verdict && (
                <p className="font-sans text-[11px] text-oxford/50">
                  <span className="uppercase tracking-wide">Quality assessment</span> ·{' '}
                  {startup.review.verdict} ({QUALITY_LABELS[startup.review.verdict] ?? startup.review.verdict})
                </p>
              )}
              <p className="font-sans text-[11px] text-oxford/60">
                <span className="uppercase tracking-wide">Investment decision</span> ·{' '}
                {startup.partner!.decision} ({DECISION_LABELS[startup.partner!.decision] ?? startup.partner!.decision})
              </p>
              {startup.timestamps?.partnered_at && (
                <p className="font-sans text-[10px] tabular-nums text-oxford/40">
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
                <p className="font-sans text-[13px] text-oxford/75 leading-relaxed pt-1">
                  {startup.partner!.rationale}
                </p>
              )}
              {startup.partner!.next_action && (
                <p className="font-sans text-[12px] text-oxford/55 pt-1">
                  <span className="uppercase tracking-wide">Next</span> · {startup.partner!.next_action}
                </p>
              )}
            </div>
          </section>
        )}
      </div>

      {onClose && (
        <div className="flex-none pt-6 mt-4 border-t border-oxford/[0.06]">
          <button
            type="button"
            onClick={onClose}
            className="min-h-[44px] px-4 font-mono text-[10px] uppercase tracking-[0.22em] text-oxford/60 hover:text-oxford active:opacity-80 transition-colors duration-300 rounded-none"
          >
            Close
          </button>
        </div>
      )}
    </div>
  );
}
