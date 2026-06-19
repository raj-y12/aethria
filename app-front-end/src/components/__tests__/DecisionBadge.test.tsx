import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import DecisionBadge, { DECISION_BADGE_LABEL } from '../DecisionBadge';

describe('DecisionBadge', () => {
  it('renders the INVEST verdict label', () => {
    render(<DecisionBadge variant="INVEST" />);
    expect(screen.getByText(DECISION_BADGE_LABEL.INVEST)).toBeInTheDocument();
  });

  it('renders pipeline-state labels for non-verdict variants', () => {
    render(<DecisionBadge variant="awaiting" />);
    expect(screen.getByText('AWAITING REVIEW')).toBeInTheDocument();
  });

  it('honours an explicit label override', () => {
    render(<DecisionBadge variant="MONITOR" label="Custom" />);
    expect(screen.getByText('Custom')).toBeInTheDocument();
  });

  it('applies a configured badge background colour for verdict variants', () => {
    render(
      <DecisionBadge
        variant="INVEST"
        badges={[
          {
            id: 'INVEST',
            label: 'Invest',
            backgroundColor: '#0a5',
          },
        ]}
      />,
    );
    const el = screen.getByText(DECISION_BADGE_LABEL.INVEST);
    // The colour is applied somewhere on the badge element or an ancestor.
    const withBg = el.closest('[style*="background"]');
    expect(withBg).not.toBeNull();
  });
});
