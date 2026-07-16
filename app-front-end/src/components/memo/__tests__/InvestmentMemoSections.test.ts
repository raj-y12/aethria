import { describe, expect, it } from 'vitest';
import memoSource from '../../InvestmentMemoContent.tsx?raw';

describe('Investment memo section order', () => {
  it('promotes thesis alignment to section 05 and moves risks to section 06', () => {
    expect(memoSource).toMatch(
      /<MemoSectionTitle number="05" id="memo-thesis-alignment">Thesis alignment<\/MemoSectionTitle>/,
    );
    expect(memoSource).toMatch(
      /<MemoSectionTitle number="06" id="memo-risk-register">Risks<\/MemoSectionTitle>/,
    );
  });

  it('uses the canonical opportunity workspace as the only human ruling path', () => {
    expect(memoSource).not.toContain('resolveEscalation');
    expect(memoSource).not.toContain('<MemoRulingSection');
    expect(memoSource.indexOf('<OpportunityIntelligence')).toBeLessThan(
      memoSource.indexOf('memoAppendixLabel'),
    );
  });
});
