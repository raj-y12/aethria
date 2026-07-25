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

  it('applies a configured badge colour as a fill for verdict variants', () => {
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
    // Configured colour is the chip's fill — verdicts render as cooled, filled chips.
    expect(el).toHaveStyle({ backgroundColor: '#0a5' });
    expect(el.style.borderColor).toBe('');
  });

  it('renders the escalation badge with its filled, full-strength background class', () => {
    render(<DecisionBadge variant="escalation" />);
    const el = screen.getByText(DECISION_BADGE_LABEL.escalation);
    // Escalation is the one variant that stays filled at full saturation,
    // regardless of any configured verdict-badge colour.
    expect(el.className).toContain('bg-escalation');
    expect(el.className).toContain('!text-white');
  });
});
