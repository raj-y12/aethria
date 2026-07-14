import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { LookupResultSnapshot } from '@aethria/product-chrome';

const baseProps = {
  companyName: 'Simantic',
  verdict: 'Invest',
  summary: 'A detailed investment finding that should remain readable without dominating the result card.',
  dimensions: [],
};

describe('LookupResultSnapshot summary typography', () => {
  it('uses the balanced serif scale only for the large snapshot', () => {
    const { rerender } = render(<LookupResultSnapshot {...baseProps} size="lg" />);
    const largeSummary = screen.getByText(baseProps.summary);

    expect(largeSummary).toHaveClass('pc-font-display');
    expect(largeSummary).toHaveClass('text-[clamp(1rem,1.8vw,1.125rem)]');
    expect(largeSummary).toHaveClass('leading-[1.4]');

    rerender(<LookupResultSnapshot {...baseProps} />);
    const defaultSummary = screen.getByText(baseProps.summary);

    expect(defaultSummary).toHaveClass('font-sans');
    expect(defaultSummary).toHaveClass('text-[15px]');
    expect(defaultSummary).not.toHaveClass('text-[clamp(1rem,1.8vw,1.125rem)]');
  });
});
