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

  it('applies a configured badge colour as a border tint (not a fill) for verdict variants', () => {
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
    // Configured colour becomes a border tint on an otherwise-transparent chip —
    // marketing parity: verdict reads by label, not fill colour.
    expect(el).toHaveStyle({ borderColor: '#0a5' });
    expect(el.style.backgroundColor).toBe('');
  });

  it('marks the escalation badge fill with !important (regression: bg-transparent cascade)', () => {
    render(<DecisionBadge variant="escalation" />);
    const el = screen.getByText(DECISION_BADGE_LABEL.escalation);
    // The base VERDICT_CHIP_CLASS carries bg-transparent, and in the compiled
    // stylesheet .bg-transparent happens to win at equal specificity — the
    // fill must be marked !bg-escalation so !important forces it regardless
    // of source order.
    expect(el.className).toContain('!bg-escalation');
  });
});
