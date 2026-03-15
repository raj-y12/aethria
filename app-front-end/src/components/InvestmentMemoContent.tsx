import { useCallback, forwardRef, useImperativeHandle } from 'react';
import { motion } from 'framer-motion';
import { jsPDF } from 'jspdf';
import type { SingleReview, Startup } from '../types/startup';
import {
  getScoreBand,
  QUALITY_LABELS,
  DECISION_LABELS,
  SCORE_DIMENSIONS,
} from '../design-system/semantics';
import { tokens } from '../design-system/tokens';
import DecisionBadge from './DecisionBadge';

const PDF_MARGIN = 20;
const PDF_LINE_HEIGHT = 5;
const PDF_FONT_SIZE_TITLE = 16;
const PDF_FONT_SIZE_HEADING = 11;
const PDF_FONT_SIZE_BODY = 10;
const PDF_FONT_SIZE_SMALL = 9;

function addPDFSection(
  doc: jsPDF,
  opts: { title?: string; lines: string[]; startY: number }
): number {
  let y = opts.startY;
  const pageH = doc.internal.pageSize.getHeight();
  const maxW = doc.internal.pageSize.getWidth() - PDF_MARGIN * 2;
  if (opts.title) {
    doc.setFontSize(PDF_FONT_SIZE_HEADING);
    doc.setTextColor(80, 80, 100);
    doc.text(opts.title, PDF_MARGIN, y);
    y += PDF_LINE_HEIGHT;
  }
  doc.setFontSize(PDF_FONT_SIZE_BODY);
  doc.setTextColor(0, 33, 71);
  for (const line of opts.lines) {
    const split = doc.splitTextToSize(line, maxW);
    for (const s of split) {
      if (y > pageH - 20) {
        doc.addPage();
        y = PDF_MARGIN;
      }
      doc.text(s, PDF_MARGIN, y);
      y += PDF_LINE_HEIGHT;
    }
  }
  return y + PDF_LINE_HEIGHT;
}

function buildMemoPDF(startup: Startup): jsPDF {
  const doc = new jsPDF({ unit: 'mm', format: 'a4' });
  let y = PDF_MARGIN;

  doc.setFontSize(PDF_FONT_SIZE_SMALL);
  doc.setTextColor(80, 80, 100);
  doc.text('Investment memo', PDF_MARGIN, y);
  y += PDF_LINE_HEIGHT;
  doc.setFontSize(PDF_FONT_SIZE_TITLE);
  doc.setTextColor(0, 33, 71);
  doc.text(startup.scout.name ?? '—', PDF_MARGIN, y);
  y += PDF_LINE_HEIGHT + 2;
  doc.setFontSize(PDF_FONT_SIZE_SMALL);
  doc.setTextColor(80, 80, 100);
  doc.text(startup.scout.sector ?? '—', PDF_MARGIN, y);
  y += PDF_LINE_HEIGHT * 2;

  const judgmentSummary = startup.partner
    ? (() => {
        const p = startup.partner!;
        const r = startup.review;
        const decisionLabel = DECISION_LABELS[p.decision] ?? p.decision;
        const quality = r?.verdict ? QUALITY_LABELS[r.verdict] ?? r.verdict : '';
        const rationale = p.rationale ?? '';
        return rationale ? `${decisionLabel}. ${rationale}` : `${decisionLabel}. Quality: ${quality}.`;
      })()
    : '';
  if (judgmentSummary) {
    const judgmentLines = judgmentToParagraphs(judgmentSummary);
    y = addPDFSection(doc, {
      title: 'Investment judgment',
      lines: judgmentLines,
      startY: y,
    });
  }

  const overviewLines: string[] = [];
  if (startup.scout.problem) overviewLines.push(`Problem: ${startup.scout.problem}`);
  if (startup.scout.solution) overviewLines.push(`Solution: ${startup.scout.solution}`);
  if (startup.scout.target_users) overviewLines.push(`Target: ${startup.scout.target_users}`);
  if (startup.scout.why_now) overviewLines.push(`Why now: ${startup.scout.why_now}`);
  if (overviewLines.length) {
    y = addPDFSection(doc, { title: 'Overview', lines: overviewLines, startY: y });
  }

  if (startup.review) {
    const primary = SCORE_DIMENSIONS.slice(0, 2);
    const lines = primary
      .map(({ id, name }) => {
        const score = startup.review?.[id as keyof typeof startup.review];
        if (score == null || typeof score !== 'number') return null;
        const band = getScoreBand(score);
        return `${name}: ${score}/10 (${band.label})`;
      })
      .filter(Boolean) as string[];
    if (lines.length) y = addPDFSection(doc, { title: 'Primary drivers', lines, startY: y });

    const supporting = SCORE_DIMENSIONS.slice(2);
    const lines2 = supporting
      .map(({ id, name }) => {
        const score = startup.review?.[id as keyof typeof startup.review];
        if (score == null || typeof score !== 'number') return null;
        const band = getScoreBand(score);
        return `${name}: ${score}/10 (${band.label})`;
      })
      .filter(Boolean) as string[];
    if (lines2.length) y = addPDFSection(doc, { title: 'Supporting analysis', lines: lines2, startY: y });
  }

  const primaryRisks = startup.review?.diligence_red_flags ?? [];
  const secondaryRisks = (startup.review?.key_risks ?? []).filter(
    (r) => !primaryRisks.some((p) => r.includes(p) || p.includes(r))
  );
  if (primaryRisks.length || secondaryRisks.length) {
    const riskLines = [
      ...(primaryRisks.length ? ['Primary: ' + primaryRisks.join('; ')] : []),
      ...(secondaryRisks.length ? ['Secondary: ' + secondaryRisks.join('; ')] : []),
    ];
    y = addPDFSection(doc, { title: 'Risks', lines: riskLines, startY: y });
  }

  if (startup.review?.overall_summary) {
    y = addPDFSection(doc, {
      title: 'Summary',
      lines: [startup.review.overall_summary],
      startY: y,
    });
  }

  if (startup.partner) {
    const p = startup.partner;
    const decisionLine = `Investment decision: ${p.decision} (${DECISION_LABELS[p.decision] ?? p.decision})`;
    const qualityLine =
      startup.review?.verdict != null
        ? `Quality: ${startup.review.verdict} (${QUALITY_LABELS[startup.review.verdict] ?? startup.review.verdict})`
        : '';
    const lines = [decisionLine, ...(qualityLine ? [qualityLine] : []), ...(p.rationale ? [p.rationale] : [])];
    y = addPDFSection(doc, { title: 'Decision', lines, startY: y });
  }

  return doc;
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

/** Split judgment text into display paragraphs. Preserves existing newlines; otherwise breaks on sentence boundaries. */
function judgmentToParagraphs(text: string): string[] {
  const trimmed = text.trim();
  if (!trimmed) return [];
  // Already has paragraph breaks (double newline)
  if (/\n\s*\n/.test(trimmed)) {
    return trimmed.split(/\n\s*\n/).map((s) => s.trim()).filter(Boolean);
  }
  // Single newlines: treat each line as a paragraph
  if (trimmed.includes('\n')) {
    return trimmed.split('\n').map((s) => s.trim()).filter(Boolean);
  }
  // No newlines: split on sentence boundary (period + space + uppercase) so we don't break "e.g." or "No."
  const sentences = trimmed.split(/(?<=\.)\s+(?=[A-Z])/).map((s) => s.trim()).filter(Boolean);
  return sentences.length ? sentences : [trimmed];
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

export interface InvestmentMemoContentHandle {
  downloadPDF: () => void;
}

const actionBtnCls = 'type-label-tab text-oxford/60 hover:text-oxford min-h-[44px] flex items-center px-2 btn-interaction';

/**
 * Memo body only. Used in full-screen modal and in the right-side panel.
 * When embedded, ref can be used to call downloadPDF() from the parent (e.g. panel header).
 */
const InvestmentMemoContent = forwardRef<InvestmentMemoContentHandle, InvestmentMemoContentProps>(function InvestmentMemoContent(
  { startup, onClose, embedded = false },
  ref
) {
  const hasReview = startup.review != null;
  const hasPartner = startup.partner != null;
  const judgmentSummary = hasPartner ? buildJudgmentSummary(startup) : null;
  const scoreJustification = hasReview ? buildScoreJustification(startup) : null;

  const companyName = startup.scout.name ?? '';

  const primaryRisks = startup.review?.diligence_red_flags ?? [];
  const secondaryRisks = (startup.review?.key_risks ?? []).filter(
    (r) => !primaryRisks.some((p) => r.includes(p) || p.includes(r))
  );

  const wrapperCls = embedded
    ? 'flex flex-col h-full min-h-0'
    : 'flex flex-col';

  const handleDownloadPDF = useCallback(() => {
    const doc = buildMemoPDF(startup);
    const safeName = (startup.scout.name ?? 'memo').replace(/[^a-zA-Z0-9-_]/g, '_').slice(0, 60);
    doc.save(`${safeName}-investment-memo.pdf`);
  }, [startup]);

  useImperativeHandle(ref, () => ({ downloadPDF: handleDownloadPDF }), [handleDownloadPDF]);

  return (
    <div className={wrapperCls}>
      {onClose && (
        <div className="flex-none flex items-center justify-end gap-2 pb-4 border-b border-oxford/[0.06]">
          <button type="button" onClick={handleDownloadPDF} className={actionBtnCls}>
            Download PDF
          </button>
          <button type="button" onClick={onClose} className={actionBtnCls}>
            Close
          </button>
        </div>
      )}
      <div className="flex-1 min-h-0 flex flex-col bg-paper">
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: tokens.motion.duration.short, ease: tokens.motion.ease }}
      >
        <p className="type-label-section text-oxford/60 mb-1">
          Investment memo
        </p>
        <h1 id="memo-title" className="type-title font-semibold text-oxford mb-1">
          {companyName}
        </h1>
        <p className="type-label-section text-oxford/60 mb-6">
          {startup.scout.sector || '—'}
        </p>
      </motion.div>

      <div className={`flex-1 min-h-0 overflow-y-auto ${embedded ? 'pr-1' : ''}`}>
        {judgmentSummary && (
          <section className="mb-6 p-4 border border-oxford/[0.08] bg-oxford/[0.04]">
            <h2 className="type-label-section text-oxford/60 mb-3">
              Investment judgment
            </h2>
            <div className="type-body text-oxford/80 leading-relaxed space-y-3">
              {judgmentToParagraphs(judgmentSummary).map((para, i) => (
                <p key={i} className="m-0">
                  {para}
                </p>
              ))}
            </div>
          </section>
        )}

        <section className="mb-6">
          <h2 className="type-label-section text-oxford/60 mb-3">
            Overview
          </h2>
          <div className="space-y-4">
            {startup.scout.problem && (
              <div>
                <p className="type-label-section text-oxford/60 mb-1">Problem</p>
                <p className="type-body text-oxford/80 leading-relaxed">{startup.scout.problem}</p>
              </div>
            )}
            {startup.scout.solution && (
              <div>
                <p className="type-label-section text-oxford/60 mb-1">Solution</p>
                <p className="type-body text-oxford/80 leading-relaxed">{startup.scout.solution}</p>
              </div>
            )}
            {startup.scout.target_users && (
              <div>
                <p className="type-label-section text-oxford/60 mb-1">Target</p>
                <p className="type-body text-oxford/80 leading-relaxed">{startup.scout.target_users}</p>
              </div>
            )}
            {startup.scout.why_now && (
              <div>
                <p className="type-label-section text-oxford/60 mb-1">Why now</p>
                <p className="type-body text-oxford/80 leading-relaxed">{startup.scout.why_now}</p>
              </div>
            )}
          </div>
        </section>

        {hasReview && startup.review?.reviewer_disagreement && Array.isArray(startup.review.reviews) && startup.review.reviews.length > 0 && (
          <section className="mb-6 pt-6 border-t border-oxford/[0.06]">
            <h2 className="type-label-section text-oxford/60 mb-3">
              Reviewer divergence
            </h2>
            <div className="overflow-x-auto no-scrollbar border border-oxford/[0.06]">
              <table className="w-full border-collapse text-left">
                <thead className="bg-ivory/60">
                  <tr>
                    <th className="px-3 py-2 type-label-section text-oxford/60">
                      Reviewer
                    </th>
                    {SCORE_DIMENSIONS.map(({ id, name }) => (
                      <th key={id} className="px-3 py-2 type-label-section text-oxford/60">
                        {name}
                      </th>
                    ))}
                    <th className="px-3 py-2 type-label-section text-oxford/60">
                      Verdict
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {startup.review.reviews.map((rev: SingleReview, idx) => (
                    <tr key={rev.reviewer_type + idx} className="border-t border-oxford/[0.06]">
                      <td className="px-3 py-2 type-body text-oxford/80 whitespace-nowrap">
                        {rev.reviewer_type.replace('Reviewer', '')}
                      </td>
                      {SCORE_DIMENSIONS.map(({ id }) => {
                        const score = (rev as any)[id] as number | undefined;
                        return (
                          <td
                            key={id}
                            className="px-3 py-2 type-body text-oxford/80 tabular-nums text-center"
                          >
                            {score != null ? score.toFixed(0) : '—'}
                          </td>
                        );
                      })}
                      <td className="px-3 py-2 type-body text-oxford/80 whitespace-nowrap">
                        {rev.verdict}
                      </td>
                    </tr>
                  ))}
                  {startup.review.score_variance && (
                    <tr className="border-t border-oxford/[0.06] bg-ivory/40">
                      <td className="px-3 py-2 type-label-section text-oxford/60">
                        Variance
                      </td>
                      {SCORE_DIMENSIONS.map(({ id }) => {
                        const v = startup.review?.score_variance?.[id] ?? 0;
                        const high = v > 1.5;
                        return (
                          <td
                            key={id}
                            className={`px-3 py-2 type-meta tabular-nums text-right ${
                              high ? 'text-oxford/80' : 'text-oxford/40'
                            }`}
                          >
                            {v ? v.toFixed(2) : '—'}
                          </td>
                        );
                      })}
                      <td />
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </section>
        )}

        {hasReview && (
          <section className="mb-6 pt-6 border-t border-oxford/[0.06]">
            <h2 className="type-label-section text-oxford/60 mb-1">
              Primary drivers
            </h2>
            <p className="type-meta text-oxford/40 mb-3">
              1–3: Weak · 4–5: Concerning · 6–7: Promising · 8–10: Strong
            </p>
            <div className="space-y-4">
              {SCORE_DIMENSIONS.slice(0, 2).map(({ id, name }) => {
                const score = startup.review?.[id as keyof typeof startup.review];
                if (score == null || typeof score !== 'number') return null;
                const band = getScoreBand(score);
                const reasoning = startup.review?.score_reasoning?.[id];
                return (
                  <div key={id} className="flex flex-col sm:flex-row sm:items-baseline gap-1 sm:gap-4">
                    <div className="sm:w-36 shrink-0">
                      <span className="type-body text-oxford/80">{name} </span>
                      <span className="type-body text-oxford/80 tabular-nums">{score}/10</span>
                      <span className="type-label-section text-oxford/60 ml-1">({band.label})</span>
                    </div>
                    {reasoning && (
                      <p className="type-body text-oxford/80 leading-relaxed">{reasoning}</p>
                    )}
                  </div>
                );
              })}
            </div>
          </section>
        )}

        {hasReview && (
          <section className="mb-6 pt-6 border-t border-oxford/[0.06]">
            <h2 className="type-label-section text-oxford/60 mb-3">
              Supporting analysis
            </h2>
            <div className="space-y-4">
              {SCORE_DIMENSIONS.slice(2).map(({ id, name }) => {
                const score = startup.review?.[id as keyof typeof startup.review];
                if (score == null || typeof score !== 'number') return null;
                const band = getScoreBand(score);
                const reasoning = startup.review?.score_reasoning?.[id];
                return (
                  <div key={id} className="flex flex-col sm:flex-row sm:items-baseline gap-1 sm:gap-4">
                    <div className="sm:w-36 shrink-0">
                      <span className="type-body text-oxford/80">{name} </span>
                      <span className="type-body text-oxford/80 tabular-nums">{score}/10</span>
                      <span className="type-label-section text-oxford/60 ml-1">({band.label})</span>
                    </div>
                    {reasoning && (
                      <p className="type-body text-oxford/80 leading-relaxed">{reasoning}</p>
                    )}
                  </div>
                );
              })}
            </div>
            {scoreJustification && (
              <p className="type-body text-oxford/80 leading-relaxed italic mt-3">
                {scoreJustification}
              </p>
            )}
          </section>
        )}

        {(primaryRisks.length > 0 || secondaryRisks.length > 0) && (
          <section className="mb-6 pt-6 border-t border-oxford/[0.06]">
            <h2 className="type-label-section text-oxford/60 mb-3">
              Risks
            </h2>
            <div className="space-y-4">
              {primaryRisks.length > 0 && (
                <div>
                  <p className="type-label-section text-oxford/60 mb-2">
                    Primary
                  </p>
                  <ul className="space-y-1 type-body text-oxford/80 leading-relaxed">
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
                  <p className="type-label-section text-oxford/60 mb-2">
                    Secondary
                  </p>
                  <ul className="space-y-1 type-body text-oxford/80 leading-relaxed">
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
            <h2 className="type-label-section text-oxford/60 mb-3">
              Summary
            </h2>
            <p className="type-body text-oxford/80 leading-relaxed">
              {startup.review.overall_summary}
            </p>
          </section>
        )}

        {startup.scout.references && startup.scout.references.length > 0 && (
          <section className="mb-6 pt-6 border-t border-oxford/[0.06]">
            <h2 className="type-label-section text-oxford/60 mb-3">
              References
            </h2>
            <ul className="space-y-1 type-body text-oxford/80 leading-relaxed">
              {startup.scout.references.map((ref, i) => (
                <li key={i} className="flex gap-2">
                  <span className="text-oxford/40">·</span>
                  <span>{ref}</span>
                </li>
              ))}
            </ul>
          </section>
        )}

        {hasPartner && (
          <section className="mt-6 pt-6 border-t border-oxford/[0.06]">
            <h2 className="type-label-section text-oxford/60 mb-3">
              Decision
            </h2>
            <div className="pl-4 border-l-2 border-oxford/40 space-y-3">
              {hasReview && startup.review?.verdict && (
                <p className="type-body text-oxford/80">
                  <span className="type-label-section text-oxford/60 uppercase tracking-wide">Quality assessment</span> ·{' '}
                  {startup.review.verdict} ({QUALITY_LABELS[startup.review.verdict] ?? startup.review.verdict})
                </p>
              )}
              <p className="type-body text-oxford/80 flex items-center gap-2 flex-wrap">
                <span className="type-label-section text-oxford/60 uppercase tracking-wide">Investment decision</span>
                <span className="inline-block scale-110 origin-left">
                  <DecisionBadge
                    variant={
                      startup.partner!.decision === 'YES'
                        ? 'YES'
                        : startup.partner!.decision === 'NO' || startup.partner!.decision === 'PASS'
                          ? 'NO'
                          : 'MAYBE'
                    }
                  />
                </span>
              </p>
              {startup.timestamps?.partnered_at && (
                <p className="type-meta tabular-nums text-oxford/40">
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
                <div className="type-body text-oxford/80 leading-relaxed space-y-3 pt-1">
                  {judgmentToParagraphs(startup.partner!.rationale).map((para, i) => (
                    <p key={i} className="m-0">
                      {para}
                    </p>
                  ))}
                </div>
              )}
              {startup.partner!.next_action && (
                <p className="type-body text-oxford/80 pt-1">
                  <span className="type-label-section text-oxford/60">Next</span> · {startup.partner!.next_action}
                </p>
              )}
              {startup.partner!.portfolio_context_at_decision && (
                <div className="mt-4 border-t border-oxford/[0.06] pt-3">
                  <p className="type-label-section text-oxford/60 mb-1">
                    Portfolio context at decision
                  </p>
                  <p className="type-body text-oxford/80">
                    Total portfolio size at decision:{' '}
                    {startup.partner!.portfolio_context_at_decision.total_portfolio_size}
                  </p>
                  {startup.scout.sector && (
                    <p className="type-body text-oxford/80">
                      Sector peers in portfolio:{' '}
                      {startup.partner!.portfolio_context_at_decision.sector_counts[startup.scout.sector] ?? 0}
                    </p>
                  )}
                  {startup.partner!.rationale &&
                    startup.partner!.rationale.toLowerCase().includes('concentration') && (
                      <p className="type-body text-oxford/80 italic mt-1">
                        Sector concentration risk was explicitly considered in this decision.
                      </p>
                    )}
                </div>
              )}
              {startup.partner!.llm_fallback_reason && (
                <p className="type-meta text-oxford/40 mt-3">
                  LLM-assisted · {startup.partner!.llm_fallback_reason}
                </p>
              )}
            </div>
          </section>
        )}
        <section className="mt-6 pt-4 border-t border-oxford/[0.06]">
          <p className="type-meta text-oxford/40">
            Scout {startup.scout.prompt_version ?? '—'} · Partner {startup.partner?.prompt_version ?? '—'}
          </p>
        </section>
      </div>
      </div>
    </div>
  );
});

export default InvestmentMemoContent;
