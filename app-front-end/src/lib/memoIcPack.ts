/**
 * IC-style memo export: PDF pack sections and pipeline replay metadata.
 */
import type { jsPDF } from 'jspdf';
import type { Startup } from '../types/startup';
import { getNextStepText, judgmentToParagraphs, parseNextStepItems } from './memoText';
import {
  DECISION_LABELS,
  QUALITY_LABELS,
  getReviewerQualityBand,
  getScoreBand,
  SCORE_DIMENSIONS,
} from '../design-system/semantics';

const PDF_MARGIN = 18;
const PDF_LINE_HEIGHT = 5;
const PDF_FONT_SIZE_TITLE = 21;
const PDF_FONT_SIZE_HEADING = 10;
const PDF_FONT_SIZE_BODY = 10;
const PDF_FONT_SIZE_SMALL = 8;

// Editorial palette (matches the app's paper/oxford ink language).
type RGB = [number, number, number];
const INK: RGB = [13, 27, 53];
const MUTED: RGB = [110, 116, 130];
const RULE: RGB = [212, 215, 222];
const TRACK: RGB = [232, 234, 239];

// Score-band ramp, keyed by getScoreBand().label.
const BAND_COLOR: Record<string, RGB> = {
  Weak: [178, 58, 47],
  Concerning: [183, 121, 31],
  Promising: [47, 96, 140],
  Strong: [46, 110, 78],
};

function decisionColor(rec?: string | null): RGB {
  const r = (rec ?? '').toUpperCase();
  if (r.includes('INVEST') || r.includes('YES')) return BAND_COLOR.Strong;
  if (r.includes('MONITOR') || r.includes('MAYBE')) return BAND_COLOR.Concerning;
  if (r.includes('PASS') || r.includes('NO')) return BAND_COLOR.Weak;
  return MUTED;
}

export interface IcSection {
  title: string;
  lines: string[];
}

export interface PipelineReplayStep {
  id: string;
  label: string;
  atIso?: string;
  atDisplay: string;
  detail: string;
  done: boolean;
}

function fmtDate(iso?: string | null): string {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString('en-GB', { dateStyle: 'medium', timeStyle: 'short' });
  } catch {
    return String(iso);
  }
}

function shortPrompt(v?: string | null): string {
  if (!v || !String(v).trim()) return '';
  const s = String(v).trim();
  return s.length <= 10 ? s : `${s.slice(0, 8)}…`;
}


function buildJudgmentLines(startup: Startup): string[] {
  if (!startup.partner) return [];
  const p = startup.partner;
  const decisionLabel = DECISION_LABELS[p.recommendation] ?? p.recommendation;
  const band = getReviewerQualityBand(startup.review);
  const dossier =
    band != null ? ` Dossier read: ${band} (${QUALITY_LABELS[band] ?? band}).` : '';
  const rationale = (p.decision_rationale ?? '').trim();
  const head = `${decisionLabel}.${dossier}`.replace(/\.\s*\./g, '.').trim();
  const combined = rationale ? `${head} ${rationale}` : head;
  return judgmentToParagraphs(combined);
}

export function getPipelineReplaySteps(startup: Startup): PipelineReplayStep[] {
  const scoutPv = shortPrompt(startup.scout.prompt_version);
  const steps: PipelineReplayStep[] = [
    {
      id: 'scout',
      label: 'Scout',
      atIso: startup.timestamps?.discovered_at,
      atDisplay: fmtDate(startup.timestamps?.discovered_at),
      detail: [
        startup.scout.scout_type || 'Scout',
        scoutPv ? `Prompt ${scoutPv}` : '',
      ]
        .filter(Boolean)
        .join(' · '),
      done: true,
    },
    {
      id: 'review',
      label: 'Review',
      atIso: startup.timestamps?.reviewed_at,
      atDisplay: fmtDate(startup.timestamps?.reviewed_at),
      detail: startup.review
        ? [
            `Verdict ${startup.review.consensus_verdict ?? startup.review.verdict ?? '—'}`,
            startup.review.reviews?.[0]?.prompt_version
              ? `Prompt ${shortPrompt(startup.review.reviews[0].prompt_version)}`
              : '',
          ]
            .filter(Boolean)
            .join(' · ')
        : 'Pending',
      done: !!startup.review,
},
    {
      id: 'partner',
      label: 'Partner',
      atIso: startup.timestamps?.partnered_at,
      atDisplay: fmtDate(startup.timestamps?.partnered_at),
      detail: startup.partner?.recommendation
        ? [
            DECISION_LABELS[startup.partner.recommendation] ?? startup.partner.recommendation,
            shortPrompt(startup.partner.prompt_version)
              ? `Prompt ${shortPrompt(startup.partner.prompt_version)}`
              : '',
          ]
            .filter(Boolean)
            .join(' · ')
        : 'Pending',
      done: !!startup.partner?.recommendation,
    },
  ];

  if (startup.human_resolution?.resolved_at) {
    steps.push({
      id: 'human',
      label: 'Human resolution',
      atIso: startup.human_resolution.resolved_at,
      atDisplay: fmtDate(startup.human_resolution.resolved_at),
      detail: [DECISION_LABELS[startup.human_resolution.decision] ?? startup.human_resolution.decision]
        .filter(Boolean)
        .join(' · '),
      done: true,
    });
  }

  return steps;
}

/**
 * Ordered sections for investment committee PDF pack.
 */
export function buildIcPackSections(startup: Startup): IcSection[] {
  const sections: IcSection[] = [];

  const exec: string[] = [];
  if (startup.scout.one_line?.trim()) exec.push(`One line: ${startup.scout.one_line.trim()}`);
  if (startup.scout.primary_thesis?.trim()) exec.push(`Thesis: ${startup.scout.primary_thesis.trim()}`);
  if (startup.scout.funding_stage?.trim()) exec.push(`Stage: ${startup.scout.funding_stage.trim()}`);
  if (startup.scout.est_tam?.trim()) exec.push(`TAM (scout est.): ${startup.scout.est_tam.trim()}`);
  if (startup.scout.biggest_unknown?.trim()) exec.push(`Biggest unknown: ${startup.scout.biggest_unknown.trim()}`);
  if (exec.length) sections.push({ title: 'Executive summary', lines: exec });

  const origin: string[] = [];
  const ot = (startup.scout.origin_type ?? '').toLowerCase();
  if (ot === 'on_demand_lookup') {
    origin.push('Channel: On-demand lookup');
    if (startup.scout.lookup_query) origin.push(`Lookup input: ${startup.scout.lookup_query}`);
    if (startup.scout.lookup_website) origin.push(`Website: ${startup.scout.lookup_website}`);
    if (startup.scout.lookup_input_type) origin.push(`Input type: ${startup.scout.lookup_input_type}`);
  } else {
    origin.push(`Channel: Scout pipeline (${startup.scout.scout_type || 'scout'})`);
  }
  origin.push(`Company ID: ${startup.id}`);
  sections.push({ title: 'Deal origin', lines: origin });

  const timelineLines = getPipelineReplaySteps(startup).map(
    (s) => `${s.label}: ${s.atDisplay} — ${s.detail}`
  );
  sections.push({ title: 'Pipeline replay (timeline)', lines: timelineLines });

  const judgment = buildJudgmentLines(startup);
  if (judgment.length) sections.push({ title: 'Investment judgment', lines: judgment });

  const overview: string[] = [];
  if (startup.scout.problem) overview.push(`Problem: ${startup.scout.problem}`);
  if (startup.scout.solution) overview.push(`Solution: ${startup.scout.solution}`);
  if (startup.scout.target_users) overview.push(`Target customers: ${startup.scout.target_users}`);
  if (startup.scout.why_now) overview.push(`Why now: ${startup.scout.why_now}`);
  if (overview.length) sections.push({ title: 'Business overview', lines: overview });

  if (startup.scout.key_assumptions?.length) {
    sections.push({
      title: 'Key assumptions',
      lines: startup.scout.key_assumptions.map((a) => `• ${a}`),
    });
  }

  if (startup.review) {
    const primary = SCORE_DIMENSIONS.slice(0, 2);
    const scoreLines = primary
      .map(({ id, name }) => {
        const score = startup.review?.[id as keyof typeof startup.review];
        if (score == null || typeof score !== 'number') return null;
        const band = getScoreBand(score);
        return `${name}: ${score}/10 (${band.label})`;
      })
      .filter(Boolean) as string[];
    const supporting = SCORE_DIMENSIONS.slice(2);
    const scoreLines2 = supporting
      .map(({ id, name }) => {
        const score = startup.review?.[id as keyof typeof startup.review];
        if (score == null || typeof score !== 'number') return null;
        const band = getScoreBand(score);
        return `${name}: ${score}/10 (${band.label})`;
      })
      .filter(Boolean) as string[];
    const allScores = [...scoreLines, ...scoreLines2];
    if (allScores.length) sections.push({ title: 'Dimension scores', lines: allScores });
  }

  const primaryRisks = startup.review?.diligence_red_flags ?? [];
  const secondaryRisks = (startup.review?.key_risks ?? []).filter(
    (r) => !primaryRisks.some((p) => r.includes(p) || p.includes(r))
  );
  if (primaryRisks.length || secondaryRisks.length) {
    sections.push({
      title: 'Risks & red flags',
      lines: [
        ...(primaryRisks.length ? [`Primary diligence: ${primaryRisks.join('; ')}`] : []),
        ...(secondaryRisks.length ? [`Additional risks: ${secondaryRisks.join('; ')}`] : []),
      ],
    });
  }

  if (startup.review?.overall_summary?.trim()) {
    sections.push({ title: 'Reviewer summary', lines: [startup.review.overall_summary.trim()] });
  }

  const dissent: string[] = [];
  if (startup.review?.reviewer_disagreement) {
    dissent.push('Multiple reviewers reported disagreement; treat verdicts with extra scrutiny.');
  }
  if (startup.review?.reviews && startup.review.reviews.length > 1) {
    const verdicts = startup.review.reviews.map((r) => r.verdict).filter(Boolean);
    if (verdicts.length) dissent.push(`Per-reviewer verdicts: ${verdicts.join(', ')}`);
  }
  if (startup.review?.assumption_feedback?.length) {
    dissent.push(
      ...startup.review.assumption_feedback.map((a) => `Assumption note: ${a}`)
    );
  }
  if (dissent.length) sections.push({ title: 'Open questions & dissent notes', lines: dissent });

  if (startup.human_resolution) {
    const hr = startup.human_resolution;
    const lines = [
      `Resolution: ${DECISION_LABELS[hr.decision] ?? hr.decision}`,
      ...(hr.notes?.trim() ? [`Notes: ${hr.notes.trim()}`] : []),
      ...(hr.resolved_at ? [`Resolved at: ${fmtDate(hr.resolved_at)}`] : []),
    ];
    sections.push({ title: 'Human resolution (escalation)', lines });
  }

  if (startup.partner) {
    const p = startup.partner;
    const nextRaw = getNextStepText(startup);
    const nextItems = parseNextStepItems(nextRaw);
    const rec: string[] = [
      `Recommendation: ${DECISION_LABELS[p.recommendation] ?? p.recommendation} (${p.recommendation})`,
    ];
    if (startup.review?.verdict) rec.push(`Reviewer quality band: ${startup.review.verdict}`);
    if (p.confidence != null) rec.push(`Partner confidence: ${Math.round(p.confidence * 100)}%`);
    if (p.human_review_required) rec.push('Flag: Human review was required before resolution.');
    if (p.decision_rationale?.trim()) rec.push(`Rationale: ${p.decision_rationale.trim()}`);
    if (nextItems.length) {
      nextItems.forEach((item, idx) => rec.push(`Next step ${idx + 1}: ${item}`));
    } else if (nextRaw) rec.push(`Next step: ${nextRaw}`);
    if (p.llm_fallback_reason) rec.push(`Engine note: ${p.llm_fallback_reason}`);
    sections.push({ title: 'Formal recommendation', lines: rec });
  }

  const appendix: string[] = [
    `Generated: ${fmtDate(new Date().toISOString())}`,
    `Discovered: ${fmtDate(startup.timestamps?.discovered_at)}`,
    `Reviewed: ${fmtDate(startup.timestamps?.reviewed_at)}`,
    `Partner decision recorded: ${fmtDate(startup.timestamps?.partnered_at)}`,
  ];
  const scoutH = startup.scout.prompt_version?.trim();
  if (scoutH) appendix.push(`Scout prompt hash: ${scoutH}`);
  const revH =
    startup.review?.reviews?.[0]?.prompt_version?.trim() ?? undefined;
  if (revH) appendix.push(`Reviewer prompt hash (primary): ${revH}`);
  const pH = startup.partner?.prompt_version?.trim();
  if (pH) appendix.push(`Partner prompt hash: ${pH}`);
  appendix.push(
    'This document was generated by Aethria for internal decision support. It is not investment advice.'
  );
  sections.push({ title: 'Appendix & data lineage', lines: appendix });

  if (startup.scout.references?.length) {
    sections.push({
      title: 'Sources',
      lines: startup.scout.references.map((r) => String(r).trim()).filter(Boolean),
    });
  }

  return sections;
}

function contentWidth(doc: jsPDF): number {
  return doc.internal.pageSize.getWidth() - PDF_MARGIN * 2;
}

/** Start a new page if `need` mm won't fit; returns the (possibly reset) y. */
function ensureSpace(doc: jsPDF, y: number, need: number): number {
  const bottom = doc.internal.pageSize.getHeight() - PDF_MARGIN - 8; // leave room for footer
  if (y + need > bottom) {
    doc.addPage();
    return PDF_MARGIN;
  }
  return y;
}

function setColor(doc: jsPDF, c: RGB): void {
  doc.setTextColor(c[0], c[1], c[2]);
}

/** Section heading: uppercase label with a hairline rule beneath. */
function drawHeading(doc: jsPDF, title: string, y: number): number {
  y = ensureSpace(doc, y, 16); // keep heading with at least one body line
  doc.setFont('helvetica', 'bold');
  doc.setFontSize(PDF_FONT_SIZE_HEADING);
  setColor(doc, INK);
  doc.text(title.toUpperCase(), PDF_MARGIN, y);
  y += 2.5;
  doc.setDrawColor(RULE[0], RULE[1], RULE[2]);
  doc.setLineWidth(0.2);
  doc.line(PDF_MARGIN, y, PDF_MARGIN + contentWidth(doc), y);
  return y + 5;
}

/** Body line; bolds a leading "Label: " prefix and hang-indents bullets. */
function drawBodyLine(doc: jsPDF, line: string, y: number): number {
  const maxW = contentWidth(doc);
  const isBullet = line.startsWith('• ');
  const indent = isBullet ? 4 : 0;
  const text = isBullet ? line.slice(2) : line;

  // Split "Label: rest" so the label can be emphasised.
  const colon = text.indexOf(': ');
  const label = colon > 0 && colon < 32 ? text.slice(0, colon + 1) : '';
  const rest = label ? text.slice(colon + 2) : text;

  doc.setFontSize(PDF_FONT_SIZE_BODY);
  const wrapped = doc.splitTextToSize((label ? `${label} ` : '') + rest, maxW - indent) as string[];

  wrapped.forEach((seg, i) => {
    y = ensureSpace(doc, y, PDF_LINE_HEIGHT);
    const x = PDF_MARGIN + indent;
    if (isBullet && i === 0) {
      setColor(doc, MUTED);
      doc.setFont('helvetica', 'normal');
      doc.text('•', PDF_MARGIN, y);
    }
    if (label && i === 0) {
      doc.setFont('helvetica', 'bold');
      setColor(doc, INK);
      doc.text(label, x, y);
      const lw = doc.getTextWidth(label) + 1.6;
      doc.setFont('helvetica', 'normal');
      setColor(doc, INK);
      // remainder of first line after the label
      const firstRest = seg.slice(label.length).trimStart();
      if (firstRest) doc.text(firstRest, x + lw, y);
    } else {
      doc.setFont('helvetica', 'normal');
      setColor(doc, INK);
      doc.text(seg, x, y);
    }
    y += PDF_LINE_HEIGHT;
  });
  return y;
}

/** Score dimensions rendered as labelled rows with a proportional band bar. */
function drawScoreBars(doc: jsPDF, startup: Startup, y: number): number {
  const barX = PDF_MARGIN + 42;
  const barW = contentWidth(doc) - 42 - 30;
  for (const { id, name } of SCORE_DIMENSIONS) {
    const score = startup.review?.[id as keyof typeof startup.review];
    if (typeof score !== 'number') continue;
    const band = getScoreBand(score);
    const color = BAND_COLOR[band.label] ?? MUTED;
    y = ensureSpace(doc, y, 8);

    doc.setFont('helvetica', 'normal');
    doc.setFontSize(PDF_FONT_SIZE_BODY);
    setColor(doc, INK);
    doc.text(name, PDF_MARGIN, y);

    doc.setFillColor(TRACK[0], TRACK[1], TRACK[2]);
    doc.roundedRect(barX, y - 3, barW, 2.4, 1.2, 1.2, 'F');
    doc.setFillColor(color[0], color[1], color[2]);
    doc.roundedRect(barX, y - 3, Math.max(2.4, (barW * score) / 10), 2.4, 1.2, 1.2, 'F');

    doc.setFont('helvetica', 'bold');
    setColor(doc, color);
    doc.text(`${score}/10`, barX + barW + 4, y);
    doc.setFont('helvetica', 'normal');
    doc.setFontSize(PDF_FONT_SIZE_SMALL);
    setColor(doc, MUTED);
    doc.text(band.label, PDF_MARGIN, y + 3.4);
    y += 8;
  }
  return y + 2;
}

/** Cover verdict strip: decision + confidence + reviewer band, accented. */
function drawVerdictStrip(doc: jsPDF, startup: Startup, y: number): number {
  const p = startup.partner;
  if (!p) return y;
  const color = decisionColor(p.recommendation);
  const w = contentWidth(doc);
  const h = 14;
  doc.setFillColor(color[0], color[1], color[2]);
  doc.rect(PDF_MARGIN, y, 1.6, h, 'F'); // accent spine
  doc.setDrawColor(RULE[0], RULE[1], RULE[2]);
  doc.setLineWidth(0.2);
  doc.rect(PDF_MARGIN + 1.6, y, w - 1.6, h, 'S');

  const tx = PDF_MARGIN + 6;
  doc.setFont('helvetica', 'bold');
  doc.setFontSize(13);
  setColor(doc, color);
  const label = DECISION_LABELS[p.recommendation] ?? p.recommendation;
  doc.text(label, tx, y + 6);

  doc.setFont('helvetica', 'normal');
  doc.setFontSize(PDF_FONT_SIZE_SMALL);
  setColor(doc, MUTED);
  const meta: string[] = [];
  if (p.confidence != null) meta.push(`Partner confidence ${Math.round(p.confidence * 100)}%`);
  const band = getReviewerQualityBand(startup.review);
  if (band != null) meta.push(`Dossier ${QUALITY_LABELS[band] ?? band}`);
  if (p.human_review_required) meta.push('Human review required');
  if (meta.length) doc.text(meta.join('   ·   '), tx, y + 11);
  return y + h + 6;
}

/** Footer with confidential mark + page numbers, drawn across all pages. */
function drawFooters(doc: jsPDF, companyName: string): void {
  const pages = doc.getNumberOfPages();
  const pageW = doc.internal.pageSize.getWidth();
  const pageH = doc.internal.pageSize.getHeight();
  const fy = pageH - 10;
  for (let i = 1; i <= pages; i++) {
    doc.setPage(i);
    doc.setDrawColor(RULE[0], RULE[1], RULE[2]);
    doc.setLineWidth(0.2);
    doc.line(PDF_MARGIN, fy - 3, pageW - PDF_MARGIN, fy - 3);
    doc.setFont('helvetica', 'normal');
    doc.setFontSize(7);
    setColor(doc, MUTED);
    doc.text('Aethria · Confidential', PDF_MARGIN, fy);
    if (companyName) doc.text(companyName, pageW / 2, fy, { align: 'center' });
    doc.text(`${i} / ${pages}`, pageW - PDF_MARGIN, fy, { align: 'right' });
  }
}

export async function buildMemoPDF(startup: Startup): Promise<jsPDF> {
  const { jsPDF: JsPDF } = await import('jspdf');
  const doc = new JsPDF({ unit: 'mm', format: 'a4' });
  let y = PDF_MARGIN + 2;

  // Masthead.
  doc.setFont('helvetica', 'bold');
  doc.setFontSize(PDF_FONT_SIZE_SMALL);
  setColor(doc, MUTED);
  doc.text('CONFIDENTIAL · INVESTMENT COMMITTEE', PDF_MARGIN, y);
  y += 8;
  doc.setFontSize(PDF_FONT_SIZE_TITLE);
  setColor(doc, INK);
  doc.text(startup.scout.name ?? 'Investment memorandum', PDF_MARGIN, y);
  y += 7;
  doc.setFont('helvetica', 'normal');
  doc.setFontSize(PDF_FONT_SIZE_BODY);
  setColor(doc, MUTED);
  const sector = startup.scout.sector?.trim() || '—';
  const stage = startup.scout.funding_stage?.trim() || '';
  doc.text(stage ? `${sector}  ·  ${stage}` : sector, PDF_MARGIN, y);
  y += 4.5;
  doc.setFontSize(PDF_FONT_SIZE_SMALL);
  doc.text(`Prepared ${fmtDate(new Date().toISOString())}`, PDF_MARGIN, y);
  y += 6;
  doc.setDrawColor(INK[0], INK[1], INK[2]);
  doc.setLineWidth(0.5);
  doc.line(PDF_MARGIN, y, PDF_MARGIN + contentWidth(doc), y);
  y += 7;

  y = drawVerdictStrip(doc, startup, y);

  for (const sec of buildIcPackSections(startup)) {
    y = drawHeading(doc, sec.title, y);
    if (sec.title === 'Dimension scores') {
      y = drawScoreBars(doc, startup, y);
    } else {
      for (const line of sec.lines) y = drawBodyLine(doc, line, y);
    }
    y += 4; // section gap
  }

  drawFooters(doc, startup.scout.name ?? '');
  return doc;
}

export function icPackSafeBaseName(startup: Startup): string {
  return (startup.scout.name ?? 'memo').replace(/[^a-zA-Z0-9-_]/g, '_').slice(0, 60);
}
