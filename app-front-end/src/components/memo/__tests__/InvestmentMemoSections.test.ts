import { describe, expect, it } from 'vitest';
import memoSource from '../../InvestmentMemoContent.tsx?raw';

describe('Investment memo section order', () => {
  it('makes founder section 02 and shifts thesis to 06 and risks to 07', () => {
    expect(memoSource).toMatch(
      /<MemoSectionTitle number="02" id="memo-founder">Founder<\/MemoSectionTitle>/,
    );
    expect(memoSource).toMatch(
      /<MemoSectionTitle number="06" id="memo-thesis-alignment">Thesis alignment<\/MemoSectionTitle>/,
    );
    expect(memoSource).toMatch(
      /<MemoSectionTitle number="07" id="memo-risk-register">Risks<\/MemoSectionTitle>/,
    );
  });

  it('uses the canonical opportunity workspace as the only human ruling path', () => {
    expect(memoSource).not.toContain('resolveEscalation');
    expect(memoSource).not.toContain('<MemoRulingSection');
    const ruling = memoSource.indexOf('<OpportunityIntelligence');
    const appendix = memoSource.indexOf('memoAppendixLabel');
    expect(ruling).toBeGreaterThan(appendix);
  });

  it('animates appendix disclosures instead of toggling hidden content abruptly', () => {
    expect(memoSource).toContain('memoDisclosureReveal');
    expect(memoSource).toContain('memoDisclosureReveal--open');
  });
});
