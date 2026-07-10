import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import MemoDossierOpening from '../MemoDossierOpening';

describe('MemoDossierOpening', () => {
  it('renders the recommendation as a lede with a compact decision record', () => {
    render(
      <MemoDossierOpening
        recommendation="Proceed"
        recommendationTone="invest"
        standfirst="The evidence supports another meeting."
        conviction="7.8 / 10"
        reviewerState="2–1 · Split"
        mandateFit="Strong"
        focalQuestion="Can distribution become repeatable?"
        blocker="Founder-led acquisition"
        nextMove="Validate three customer references"
      />,
    );

    expect(screen.getByRole('heading', { level: 2, name: 'Proceed' })).toBeInTheDocument();
    expect(screen.getByRole('complementary', { name: 'Decision record' })).toHaveTextContent(
      'Founder-led acquisition',
    );
    expect(screen.getByText('Can distribution become repeatable?')).toBeInTheDocument();
    expect(screen.getByText('Validate three customer references')).toBeInTheDocument();
  });
});
