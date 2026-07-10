import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import DispatchCommandBar from '../DispatchCommandBar';

describe('DispatchCommandBar active lookup', () => {
  it('exposes a clearly named resume control for one active analysis', () => {
    const focus = vi.fn();
    render(
      <DispatchCommandBar
        open
        onClose={() => undefined}
        input=""
        setInput={() => undefined}
        onSubmit={() => undefined}
        isBusy={false}
        message="Still reviewing"
        lookupPhase="Reviewing"
        progress={{
          query: 'Acme',
          name: 'Acme',
          sector: 'AI',
          mode: 'rerun',
          resolved: true,
          found: true,
          reviewed: true,
          decisionComplete: true,
        }}
        chips={[{ id: 'lookup-1', label: 'Acme', status: 'reviewing', active: true }]}
        onFocusChip={focus}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Back' }));
    const resume = screen.getByRole('button', { name: 'Resume active analysis for Acme' });
    fireEvent.click(resume);

    expect(focus).toHaveBeenCalledWith('lookup-1');
    expect(screen.getByLabelText('Analysis progress')).toBeInTheDocument();
    expect(screen.getByText('Memo')).toBeInTheDocument();
  });
});
