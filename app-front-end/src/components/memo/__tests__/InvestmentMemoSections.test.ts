// @vitest-environment node
// @ts-expect-error Test-only Node import; the app tsconfig intentionally exposes React types only.
import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import memoSource from '../../InvestmentMemoContent.tsx?raw';

const memoStyles = readFileSync(new URL('../../InvestmentMemoContent.css', import.meta.url), 'utf8');

function cssRuleBody(selector: string): string {
  const start = memoStyles.indexOf(`${selector} {`);
  if (start < 0) return '';
  const bodyStart = memoStyles.indexOf('{', start) + 1;
  return memoStyles.slice(bodyStart, memoStyles.indexOf('}', bodyStart));
}

function relativeLuminance([red, green, blue]: [number, number, number]): number {
  const channel = (value: number) => {
    const normalized = value / 255;
    return normalized <= 0.04045
      ? normalized / 12.92
      : ((normalized + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * channel(red) + 0.7152 * channel(green) + 0.0722 * channel(blue);
}

describe('Investment memo section order', () => {
  it('keeps the editorial memo in the primary reading flow', () => {
    expect(memoSource).not.toContain('<details className="memoSupportingAnalysis"');
    expect(memoSource).not.toContain('<summary>Supporting analysis</summary>');
    expect(memoSource).toMatch(
      /<MemoSectionTitle number="02" id="memo-founder">Founder<\/MemoSectionTitle>/,
    );
    expect(memoSource).toMatch(
      /<MemoSectionTitle number="04" id="memo-scoring">\s*\{showPriorWorkflowAnalysis \? 'Prior workflow read' : 'Assessment'\}\s*<\/MemoSectionTitle>/,
    );
    expect(memoSource).toMatch(
      /<MemoSectionTitle number="05" id="memo-thesis-alignment">Thesis alignment<\/MemoSectionTitle>/,
    );
    expect(memoSource).not.toContain('id="memo-risk-register"');
  });

  it('puts the canonical decision workspace first and removes rejected primary hierarchy', () => {
    expect(memoSource).not.toContain('resolveEscalation');
    expect(memoSource).not.toContain('<MemoRulingSection');
    const ruling = memoSource.indexOf('<OpportunityIntelligence');
    const snapshot = memoSource.indexOf('id="memo-snapshot"');
    expect(ruling).toBeGreaterThan(-1);
    expect(snapshot).toBeGreaterThan(ruling);
    expect(memoSource).not.toContain('<MemoDossierOpening');
    expect(memoSource).not.toContain('id="memo-read"');
    expect(memoSource).not.toContain('id="memo-killers"');
    expect(memoSource).not.toContain('Make your ruling <span aria-hidden>↓</span>');
  });

  it('does not expose the legacy categorical IC pack export from the redesigned memo', () => {
    expect(memoSource).not.toContain('buildMemoPDF');
    expect(memoSource).not.toContain('icPackSafeBaseName');
    expect(memoSource).not.toContain('handleDownloadPDF');
    expect(memoSource).not.toContain('onDownloadPDF=');
  });

  it('animates appendix disclosures instead of toggling hidden content abruptly', () => {
    expect(memoSource).toContain('memoDisclosureReveal');
    expect(memoSource).toContain('memoDisclosureReveal--open');
  });

  it('makes every closed animated disclosure inert until its toggle opens it', () => {
    expect(memoSource).toContain('inert={!open}');
    expect(memoSource).toContain('aria-hidden={!open}');
  });

  it('collapses the entire decision and ruling surface from the memo container width', () => {
    const containerStart = memoStyles.indexOf('@container memoPanel (max-width: 760px)');
    const nextContainer = memoStyles.indexOf('@container memoPanel (max-width: 520px)', containerStart);
    const containerRules = memoStyles.slice(containerStart, nextContainer);

    expect(containerStart).toBeGreaterThan(-1);
    expect(containerRules).toMatch(/\.memoDecisionStateGrid,[\s\S]*grid-template-columns:\s*1fr/);
    expect(containerRules).toMatch(/\.memoDecisionBriefHead[\s\S]*flex-direction:\s*column/);
    expect(containerRules.match(/\.memoConsensusRow\s*\{([^}]*)\}/)?.[1] ?? '').not.toContain(
      'grid-template-columns',
    );
    expect(containerRules).toMatch(/\.memoDecisionReasoningGrid[\s\S]*grid-template-columns:\s*1fr/);
    expect(containerRules).toMatch(/\.memoDecisionActionCreate[\s\S]*grid-template-columns:\s*1fr/);
    expect(containerRules).toMatch(/\.memoDecisionChoices[\s\S]*grid-template-columns:\s*1fr/);

    for (const selector of [
      '.memoDecisionReasoningHead',
      '.memoDecisionCallHead',
      '.memoDecisionActionsHead',
      '.memoDecisionHistoryHead',
      '.memoDecisionActionHead',
    ]) {
      expect(containerRules).toMatch(
        new RegExp(`${selector.replace('.', '\\.')}[\\s\\S]*flex-direction:\\s*column`),
      );
    }
  });

  it('keeps reviewer comparisons horizontal until the genuinely narrow breakpoint', () => {
    const narrowStart = memoStyles.indexOf('@container memoPanel (max-width: 520px)');
    const narrowRules = memoStyles.slice(narrowStart);

    expect(narrowStart).toBeGreaterThan(-1);
    expect(narrowRules).toMatch(/\.memoConsensusRow[\s\S]*grid-template-columns:\s*1fr/);
  });

  it('gives desktop reviewer scores room for coverage and permits coverage to wrap', () => {
    const reviewerRow = memoStyles.match(/\.memoConsensusRow \{\s*display: grid;([\s\S]*?)\}/)?.[1] ?? '';
    const coverage = cssRuleBody('.memoConsensusCoverage');

    expect(reviewerRow).toMatch(/grid-template-columns:[^;]*minmax\((?:9\d|1\d{2,})px/);
    expect(reviewerRow).not.toMatch(/\s(?:40|44)px\s/);
    expect(coverage).not.toContain('white-space: nowrap');
  });

  it('keeps decision action controls at least 44px tall', () => {
    const actionControls = memoStyles.match(
      /\.memoDecisionActionCreate select,[\s\S]*?\.memoDecisionApprove \{([\s\S]*?)\}/,
    )?.[1] ?? '';

    expect(actionControls).toMatch(/min-height:\s*(?:4[4-9]|[5-9]\d|\d{3,})px/);
  });

  it('uses an AA-safe metadata token for all small decision and ruling microcopy', () => {
    const token = memoStyles.match(
      /--memo-decision-meta:\s*rgba\(var\(--color-oxford-rgb\),\s*(0?\.\d+)\)/,
    );
    expect(token).not.toBeNull();

    const alpha = Number(token![1]);
    const paper: [number, number, number] = [217, 215, 212];
    const oxford: [number, number, number] = [10, 22, 41];
    const composited = oxford.map((value, index) =>
      Math.round(alpha * value + (1 - alpha) * paper[index]),
    ) as [number, number, number];
    const contrast = (relativeLuminance(paper) + 0.05) / (relativeLuminance(composited) + 0.05);

    expect(contrast).toBeGreaterThanOrEqual(4.5);
    const tokenDeclaration = 'color: var(--memo-decision-meta);';
    const tokenBodyStart = memoStyles.indexOf(tokenDeclaration);
    const tokenSelectorsStart = memoStyles.lastIndexOf('\n\n', tokenBodyStart) + 2;
    const tokenSelectors = memoStyles.slice(tokenSelectorsStart, tokenBodyStart);

    expect(tokenBodyStart).toBeGreaterThan(-1);
    for (const selector of [
      '.memoDecisionEyebrow',
      '.memoDecisionMeta',
      '.memoDecisionStatus',
      '.memoDecisionLean > p',
      '.memoDecisionChecks dt',
      '.memoDecisionDrivers li::before',
      '.memoDecisionMaterialProvenance',
      '.memoDecisionSourceMissing',
      '.memoDecisionMuted',
      '.memoDecisionRiskMeta',
      '.memoDecisionProvenanceMeta',
      '.memoDecisionSources',
      '.memoDecisionChangeCondition span',
      '.memoDecisionDisclosure summary',
      '.memoDecisionOverride',
      '.memoDecisionHistoryList em',
      '.memoDecisionHistoryList small',
      '.memoDecisionActionHead p',
      '.memoDecisionActionHead span',
      '.memoRulingSubmit:disabled',
    ]) {
      expect(tokenSelectors).toContain(selector);
    }
  });

});
