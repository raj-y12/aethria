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
});
