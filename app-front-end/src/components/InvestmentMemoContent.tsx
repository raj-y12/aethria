import { useCallback, forwardRef, useEffect, useImperativeHandle, useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import { jsPDF } from 'jspdf';
import type { Startup } from '../types/startup';
import {
  getScoreBand,
  DECISION_LABELS,
  SCORE_DIMENSIONS,
} from '../design-system/semantics';

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
        const decisionLabel = DECISION_LABELS[p.decision] ?? p.decision;
        const rationale = p.rationale ?? '';
        return rationale ? `${decisionLabel}. ${rationale}` : `${decisionLabel}.`;
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
    const qualityLine = startup.review?.verdict != null ? `Quality: ${startup.review.verdict}` : '';
    const lines = [decisionLine, ...(qualityLine ? [qualityLine] : []), ...(p.rationale ? [p.rationale] : [])];
    y = addPDFSection(doc, { title: 'Decision', lines, startY: y });
  }

  return doc;
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
  startup: Startup | null;
  onClose?: () => void;
  /** When true, used in side panel (no outer padding; panel provides it). */
  embedded?: boolean;
}

export interface InvestmentMemoContentHandle {
  downloadPDF: () => void;
}

function normalizeParagraphs(value: unknown): string[] {
  if (value == null) return [];
  if (Array.isArray(value)) {
    return value
      .map((v) => String(v ?? '').replace(/\s*\n+\s*/g, ' ').trim())
      .filter(Boolean)
      .flatMap((v) => [v]);
  }
  if (typeof value === 'string') return [value.replace(/\s*\n+\s*/g, ' ').trim()].filter(Boolean);
  return [];
}

function toJudgmentVerdict(startup: Startup): string {
  const d = startup.partner?.decision;
  if (d === 'YES') return 'STRONG';
  if (d === 'NO' || d === 'PASS') return 'PASS';
  return 'HOLD';
}

function toJudgmentReasoning(startup: Startup): string[] {
  const rationale = startup.partner?.rationale;
  if (!rationale) return [];
  return normalizeParagraphs(rationale);
}

function formatSectorAndCategory(startup: Startup): string {
  const sector = startup.scout.sector?.trim() || '—';
  const category = startup.scout.funding_stage?.trim() || startup.scout.scout_type?.trim() || '';
  return category ? `${sector} · ${category}` : sector;
}

const actionBtnCls = 'memoAction';

/**
 * Memo body only. Used in full-screen modal and in the right-side panel.
 * When embedded, ref can be used to call downloadPDF() from the parent (e.g. panel header).
 */
const InvestmentMemoContent = forwardRef<InvestmentMemoContentHandle, InvestmentMemoContentProps>(function InvestmentMemoContent(
  { startup, onClose, embedded = false },
  ref
) {
  const wrapperCls = embedded ? 'memoPanel memoPanel--embedded' : 'memoPanel';
  const [selectedDimensionIdx, setSelectedDimensionIdx] = useState(0);
  const [sourcesOpen, setSourcesOpen] = useState(false);

  const handleDownloadPDF = useCallback(() => {
    if (!startup) return;
    const doc = buildMemoPDF(startup);
    const safeName = (startup.scout.name ?? 'memo').replace(/[^a-zA-Z0-9-_]/g, '_').slice(0, 60);
    doc.save(`${safeName}-investment-memo.pdf`);
  }, [startup]);

  useImperativeHandle(ref, () => ({ downloadPDF: handleDownloadPDF }), [handleDownloadPDF]);

  const contentKey = startup?.id ?? 'empty';
  const companyName = startup?.scout.name?.trim() || '';
  const sectorCategory = startup ? formatSectorAndCategory(startup) : '';

  const showJudgment = !!startup?.review && !!startup?.partner?.decision;
  const verdict = startup && showJudgment ? toJudgmentVerdict(startup) : '';
  const reasoningParagraphs = useMemo(() => (startup && showJudgment ? toJudgmentReasoning(startup) : []), [startup, showJudgment]);

  useEffect(() => {
    setSelectedDimensionIdx(0);
    setSourcesOpen(false);
  }, [startup?.id]);

  const scoreBlocks = useMemo(() => {
    if (!startup?.review) return [];
    return SCORE_DIMENSIONS.map(({ id, name }) => {
      const score = startup.review?.[id as keyof typeof startup.review];
      const numeric = typeof score === 'number' ? score : null;
      const reasoning = startup.review?.score_reasoning?.[id]?.trim() || '';
      return { id, name, score: numeric, reasoning };
    });
  }, [startup]);

  const scoresSummary = useMemo(() => {
    if (!startup?.review) return null;
    return buildScoreJustification(startup);
  }, [startup]);

  return (
    <div className={wrapperCls}>
      <style>{`
        .memoPanel{
          width: 60%;
          min-width: 0;
          flex: 0 0 60%;
          background: #F2F0EA;
          min-height: 0;
          height: 100%;
          overflow: hidden;
          display: flex;
          flex-direction: column;
        }
        .memoPanel--embedded{
          width: 100%;
          flex: 1 1 auto;
          /* Let the parent panel own scrolling in embedded mode. */
          height: auto;
          overflow: visible;
        }
        .memoScroll{
          flex: 1 1 auto;
          min-height: 0;
          overflow-y: auto;
          overflow-x: hidden;
          padding-left: 48px;
          padding-right: 48px;
          padding-top: 36px;
          padding-bottom: 36px;
          color: #002147;
          background: #F2F0EA;
        }
        .memoPanel--embedded .memoScroll{
          /* PanelShell already applies content padding; avoid double-padding in embedded mode. */
          padding-left: 0px;
          padding-right: 0px;
          padding-top: 0px;
          padding-bottom: 0px;
          /* PanelShell already scrolls in embedded mode; avoid nested scrollbars. */
          overflow: visible;
          flex: 0 0 auto;
          min-height: auto;
        }
        .memoHeaderActions{
          display: flex;
          justify-content: flex-end;
          gap: 16px;
          margin-top: 0px;
          margin-bottom: 18px;
        }
        .memoAction{
          appearance: none;
          border: none;
          background: transparent;
          padding: 0;
          cursor: pointer;
          font-family: "Space Mono", ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
          font-size: 10px;
          font-variant-caps: all-small-caps;
          letter-spacing: 0.1em;
          color: rgba(0,33,71,0.45);
          transition: color 150ms ease;
        }
        .memoAction:hover{ color: rgba(0,33,71,1); }
        .memoCompany{
          font-family: "Geist Sans", system-ui, sans-serif;
          font-weight: 700;
          font-size: clamp(24px, 3.2vw, 32px);
          line-height: 1.2;
          margin: 0;
          color: rgba(0,33,71,0.92);
        }
        .memoHeaderDivider{
          margin-top: 13px;
          margin-bottom: 24px;
        }
        .memoSectionSpacer{
          height: 29px;
          flex-shrink: 0;
        }
        .memoMeta{
          margin-top: 4px;
          font-family: "Space Mono", ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
          font-size: 10px;
          letter-spacing: 0.1em;
          color: rgba(0,33,71,0.4);
          text-transform: uppercase;
        }
        .memoDivider{
          height: 1px;
          width: 100%;
          background: rgba(0,33,71,0.08);
        }
        .memoLabel{
          font-family: "Space Mono", ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
          font-size: 10px;
          text-transform: uppercase;
          letter-spacing: 0.14em;
          line-height: 1.5;
          color: rgba(0,33,71,0.5);
          margin: 0 0 15px 0;
          padding-bottom: 6px;
          border-bottom: none;
        }
        .memoVerdict{
          font-family: "Space Mono", ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
          font-weight: 700;
          font-size: 32px;
          line-height: 1.3;
          letter-spacing: 0.08em;
          text-transform: uppercase;
          margin: 0 0 12px 0;
          padding-top: 0px;
          padding-bottom: 0px;
          color: rgba(0,33,71,1);
        }
        .memoReasoning{
          font-family: "Geist Sans", system-ui, -apple-system, sans-serif, "Apple Color Emoji", "Segoe UI Emoji";
          font-weight: 400;
          font-size: 14px;
          line-height: 1.6;
          color: rgba(0,33,71,0.78);
        }
        .memoReasoning p{ margin: 0; }
        .memoReasoning p + p{ margin-top: 7px; }
        .memoScoresRow{
          display: grid;
          grid-template-columns: repeat(5, minmax(0, 1fr));
          gap: 18px;
        }
        .memoScoreCol{
          appearance: none;
          border: none;
          background: transparent;
          padding: 0;
          text-align: center;
          cursor: pointer;
          min-width: 0;
        }
        .memoScoreCol:focus{ outline: none; }
        .memoScoreCol:focus-visible{
          outline: 2px solid rgba(0,33,71,0.25);
          outline-offset: 4px;
        }
        .memoScoreName{
          font-family: "Space Mono", ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
          font-size: 11px;
          font-variant-caps: all-small-caps;
          letter-spacing: 0.08em;
          color: rgba(0,33,71,0.55);
          margin: 0 0 8px 0;
        }
        .memoScoreValue{
          font-family: "Space Mono", ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
          font-weight: 700;
          font-size: 28px;
          line-height: 1.5;
          margin: 0 0 8px 0;
          color: #002147;
        }
        .memoScoreValueRow{
          display: flex;
          align-items: baseline;
          justify-content: center;
          gap: 0;
        }
        .memoScoreBandLabel{
          font-family: "Space Mono", ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
          font-size: 10px;
          letter-spacing: 0.08em;
          color: rgba(0,33,71,0.4);
        }
        .memoScoreLegend{
          margin-top: 7px;
          margin-bottom: 14px;
          font-family: "Space Mono", ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
          font-size: 10px;
          line-height: 1.5;
          color: rgba(0,33,71,0.35);
        }
        .memoScoreUnderline{
          height: 2px;
          width: 100%;
          background: rgba(0,33,71,0.15);
          margin-top: 8px;
        }
        .memoScoreWhy{
          font-family: "Geist Sans", system-ui, -apple-system, sans-serif, "Apple Color Emoji", "Segoe UI Emoji";
          font-size: 12px;
          line-height: 1.6;
          color: rgba(0,33,71,0.6);
          margin: 0;
          overflow: hidden;
          display: -webkit-box;
          -webkit-line-clamp: 2;
          -webkit-box-orient: vertical;
        }
        .memoDimensionPanel{
          margin-top: 14px;
        }
        .memoDimensionPanelName{
          font-family: "Space Mono", ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
          font-size: 11px;
          font-variant-caps: all-small-caps;
          letter-spacing: 0.12em;
          color: rgba(0,33,71,0.4);
          margin: 0 0 8px 0;
        }
        .memoDimensionPanelText{
          font-family: "Geist Sans", system-ui, -apple-system, sans-serif, "Apple Color Emoji", "Segoe UI Emoji";
          font-size: 14px;
          line-height: 1.6;
          color: rgba(0,33,71,0.78);
          margin: 0;
          white-space: normal;
        }
        .memoList{
          margin: 0;
          padding: 0;
          list-style: none;
          font-family: "Geist Sans", system-ui, -apple-system, sans-serif, "Apple Color Emoji", "Segoe UI Emoji";
          font-size: 14px;
          line-height: 1.6;
          color: rgba(0,33,71,0.78);
        }
        .memoListItem{
          display: flex;
          gap: 10px;
        }
        .memoListItem + .memoListItem{ margin-top: 10px; }
        .memoBullet{ color: rgba(0,33,71,0.35); }
        .memoLink{
          color: rgba(0,33,71,0.85);
          text-decoration: none;
          border-bottom: 1px solid rgba(0,33,71,0.15);
        }
        .memoLink:hover{
          border-bottom-color: rgba(0,33,71,0.4);
        }
        .memoSummaryCallout{
          /* Match WorkGrid row hover: oxford @ 2% (Tailwind bg-oxford/[0.02]) */
          background: rgba(0, 33, 71, 0.02);
          padding: 18px;
        }
        .memoSourcesToggle{
          width: 100%;
          display: flex;
          align-items: center;
          justify-content: space-between;
          appearance: none;
          border: none;
          background: transparent;
          padding: 0;
          cursor: pointer;
          font-family: "Space Mono", ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
          font-size: 10px;
          text-transform: uppercase;
          letter-spacing: 0.14em;
          color: rgba(0,33,71,0.5);
          padding-bottom: 8px;
          border-bottom: none;
        }
        .memoSourcesPlus{
          font-family: "Space Mono", ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
          font-size: 10px;
          color: rgba(0,33,71,0.5);
          line-height: 1.5;
        }
        .memoScoresSummary{
          margin: 0 0 10px 0;
          font-family: "Geist Sans", system-ui, -apple-system, sans-serif, "Apple Color Emoji", "Segoe UI Emoji";
          font-style: italic;
          font-size: 13px;
          line-height: 1.6;
          color: rgba(0,33,71,0.5);
        }
        .memoOverviewRow{
          display: grid;
          grid-template-columns: 120px minmax(0, 1fr);
          column-gap: 24px;
          align-items: start;
        }
        .memoOverviewRow + .memoOverviewRow{ margin-top: 14px; }
        .memoOverviewKey{
          font-family: "Space Mono", ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
          font-size: 11px;
          font-variant-caps: all-small-caps;
          letter-spacing: 0.08em;
          color: rgba(0,33,71,0.55);
          margin: 0;
        }
        .memoOverviewVal{
          font-family: "Geist Sans", system-ui, -apple-system, sans-serif, "Apple Color Emoji", "Segoe UI Emoji";
          font-size: 14px;
          line-height: 1.6;
          color: rgba(0,33,71,0.78);
          margin: 0;
        }
        .memoEmpty{
          height: 100%;
          width: 100%;
          display: flex;
          align-items: center;
          justify-content: center;
          background: #F2F0EA;
        }
        .memoEmptyInner{
          text-align: center;
          padding: 48px;
        }
        .memoEmptyWordmark{
          font-family: "Libre Baskerville", Georgia, serif;
          font-weight: 400;
          font-size: 24px;
          line-height: 1.4;
          color: rgba(0,33,71,0.25);
          margin: 0;
        }
        .memoEmptyHint{
          margin-top: 12px;
          font-family: "Geist Sans", system-ui, -apple-system, sans-serif, "Apple Color Emoji", "Segoe UI Emoji";
          font-size: 13px;
          line-height: 1.6;
          color: rgba(0,33,71,0.2);
        }

        @media (max-width: 1100px){
          .memoPanel{ width: 100%; flex-basis: auto; }
          .memoScoresRow{ grid-template-columns: repeat(2, minmax(0, 1fr)); }
        }
      `}</style>

      {!startup ? (
        <div className="memoEmpty">
          <div className="memoEmptyInner">
            <p className="memoEmptyWordmark">Aethria</p>
            <div className="memoEmptyHint">Select a company to view the investment memo.</div>
          </div>
        </div>
      ) : (
        <div className="memoScroll" role="region" aria-label="Investment memo">
          {onClose && (
            <div className="memoHeaderActions">
              <button type="button" onClick={handleDownloadPDF} className={actionBtnCls}>
                DOWNLOAD PDF
              </button>
              <button type="button" onClick={onClose} className={actionBtnCls}>
                CLOSE
              </button>
            </div>
          )}

          <motion.div
            key={contentKey}
            initial={{ opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.28, ease: [0.16, 1, 0.3, 1] }}
          >
            {/* Header block */}
            <h1 id="memo-title" className="memoCompany">
              {companyName || '—'}
            </h1>
            <div className="memoMeta">{sectorCategory}</div>
            <div className="memoDivider memoHeaderDivider" aria-hidden />

            {/* Investment Judgment block */}
            {showJudgment && (
              <>
                <section>
                  <p className="memoLabel">INVESTMENT JUDGMENT</p>
                  <div className="memoVerdict">{verdict}</div>
                  <div className="memoReasoning">
                    {reasoningParagraphs.filter((p) => String(p ?? '').trim().length > 0).map((p, i) => (
                      <p key={i}>{p}</p>
                    ))}
                  </div>
                </section>

                <div className="memoSectionSpacer" aria-hidden />
              </>
            )}

            {/* Dimension Scores block */}
            <section>
              <p className="memoLabel">DIMENSION SCORES</p>
              {scoresSummary && <div className="memoScoresSummary">{scoresSummary}</div>}
              <p className="memoScoreLegend">1-3: WEAK · 4-5: CONCERNING · 6-7: PROMISING · 8-10: STRONG</p>
              <div className="memoScoresRow">
                {scoreBlocks.map((b, idx) => {
                  const isSelected = idx === selectedDimensionIdx;
                  const displayScore = b.score != null ? `${Math.round(b.score)}/10` : '—';
                  return (
                    <button
                      key={b.id}
                      type="button"
                      className="memoScoreCol"
                      onClick={() => setSelectedDimensionIdx(idx)}
                      aria-pressed={isSelected}
                    >
                      <p className="memoScoreName">{b.name}</p>
                      <div className="memoScoreValueRow">
                        <p
                          className="memoScoreValue"
                          style={{ opacity: isSelected ? 1 : 0.5, transition: 'opacity 180ms ease' }}
                        >
                          {displayScore}
                        </p>
                      </div>
                      {isSelected ? <div className="memoScoreUnderline" /> : <div style={{ height: 2, marginTop: 8 }} />}
                    </button>
                  );
                })}
              </div>

              {scoreBlocks.length > 0 && (
                <div className="memoDimensionPanel">
                  <motion.div
                    key={`${contentKey}:${selectedDimensionIdx}`}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ duration: 0.18, ease: [0.16, 1, 0.3, 1] }}
                  >
                    <p className="memoDimensionPanelName">
                      {scoreBlocks[selectedDimensionIdx]?.name ?? '—'}
                    </p>
                    <p className="memoDimensionPanelText">
                      {(() => {
                        const selected = scoreBlocks[selectedDimensionIdx];
                        if (!selected) return '—';
                        const reasoning = selected.reasoning?.trim();
                        if (reasoning) return reasoning;
                        if (selected.score != null) return getScoreBand(selected.score).meaning || '—';
                        return '—';
                      })()}
                    </p>
                  </motion.div>
                </div>
              )}
            </section>

            <div className="memoSectionSpacer" aria-hidden />

            {/* Overview block */}
            <section>
              <p className="memoLabel">OVERVIEW</p>
              <div className="memoOverviewRow">
                <p className="memoOverviewKey">PROBLEM</p>
                <p className="memoOverviewVal">{startup.scout.problem?.trim() || '—'}</p>
              </div>
              <div className="memoOverviewRow">
                <p className="memoOverviewKey">SOLUTION</p>
                <p className="memoOverviewVal">{startup.scout.solution?.trim() || '—'}</p>
              </div>
              <div className="memoOverviewRow">
                <p className="memoOverviewKey">TARGET</p>
                <p className="memoOverviewVal">{startup.scout.target_users?.trim() || '—'}</p>
              </div>
              <div className="memoOverviewRow">
                <p className="memoOverviewKey">WHY NOW</p>
                <p className="memoOverviewVal">{startup.scout.why_now?.trim() || '—'}</p>
              </div>
            </section>

            {startup.review?.overall_summary && (
              <>
                <div className="memoSectionSpacer" aria-hidden />
                <section>
                  <p className="memoLabel">SUMMARY</p>
                  <div className="memoSummaryCallout">
                    <p className="memoOverviewVal" style={{ marginTop: 0 }}>
                      {startup.review.overall_summary}
                    </p>
                  </div>
                </section>
              </>
            )}

            {(startup.review?.diligence_red_flags?.length || startup.review?.key_risks?.length) && (
              <>
                <div className="memoSectionSpacer" aria-hidden />
                <section>
                  <p className="memoLabel">RED FLAGS</p>
                  <ul className="memoList">
                    {[...(startup.review?.diligence_red_flags ?? []), ...(startup.review?.key_risks ?? [])]
                      .map((r) => String(r ?? '').trim())
                      .filter(Boolean)
                      .map((r, i) => (
                        <li key={i} className="memoListItem">
                          <span className="memoBullet">·</span>
                          <span>{r}</span>
                        </li>
                      ))}
                  </ul>
                </section>
              </>
            )}

            {startup.scout.references && startup.scout.references.length > 0 && (
              <>
                <div className="memoSectionSpacer" aria-hidden />
                <section>
                  <button
                    type="button"
                    className="memoSourcesToggle"
                    onClick={() => setSourcesOpen((v) => !v)}
                    aria-expanded={sourcesOpen}
                  >
                    <span>SOURCES</span>
                    <span className="memoSourcesPlus">{sourcesOpen ? '−' : '+'}</span>
                  </button>
                  <motion.div
                    initial={false}
                    animate={sourcesOpen ? { height: 'auto', opacity: 1 } : { height: 0, opacity: 0 }}
                    transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
                    style={{ overflow: 'hidden' }}
                  >
                    <div style={{ paddingTop: 14 }}>
                      <ul className="memoList">
                        {startup.scout.references
                          .map((r) => String(r ?? '').trim())
                          .filter(Boolean)
                          .map((ref, i) => (
                            <li key={i} className="memoListItem">
                              <span className="memoBullet">·</span>
                              <a className="memoLink" href={ref} target="_blank" rel="noreferrer">
                                {ref}
                              </a>
                            </li>
                          ))}
                      </ul>
                    </div>
                  </motion.div>
                </section>
              </>
            )}
          </motion.div>
        </div>
      )}
    </div>
  );
});

export default InvestmentMemoContent;
