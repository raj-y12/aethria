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

  it('shows accepted work before execution starts', () => {
    render(
      <DispatchCommandBar
        open
        onClose={() => undefined}
        input=""
        setInput={() => undefined}
        onSubmit={() => undefined}
        isBusy={false}
        message="Waiting for an execution slot"
        lookupPhase={null}
        progress={{ query: 'Acme', name: 'Acme', sector: 'AI', resolved: true, found: false, reviewed: false }}
        execution={{
          status: 'accepted',
          acceptedAt: '2026-07-15T12:00:00Z',
          attempts: 0,
          maxAttempts: 3,
        }}
      />,
    );

    expect(screen.getByText('Accepted')).toBeInTheDocument();
    expect(screen.getByText(/Waiting for an execution slot/i)).toBeInTheDocument();
  });

  it('keeps a blocked job actionable and routes identity review deliberately', () => {
    const retry = vi.fn();
    const identity = vi.fn();
    render(
      <DispatchCommandBar
        open
        onClose={() => undefined}
        input=""
        setInput={() => undefined}
        onSubmit={() => undefined}
        isBusy={false}
        message={null}
        lookupPhase={null}
        progress={{ query: 'Acme', name: 'Acme', sector: null, resolved: false, found: false, reviewed: false }}
        execution={{
          status: 'blocked',
          acceptedAt: '2026-07-15T12:00:00Z',
          attempts: 1,
          maxAttempts: 3,
          blockCode: 'identity_review_required',
          recoveryAction: 'Resolve the identity case, then retry this lookup job.',
        }}
        onRetryJob={retry}
        onOpenIdentityReview={identity}
      />,
    );

    expect(screen.getByText('Identity review required')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Retry job' })).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: 'Review identity' }));
    expect(identity).toHaveBeenCalledTimes(1);
  });

  it('offers retry after a dead-letter state', () => {
    const retry = vi.fn();
    render(
      <DispatchCommandBar
        open
        onClose={() => undefined}
        input=""
        setInput={() => undefined}
        onSubmit={() => undefined}
        isBusy={false}
        message={null}
        lookupPhase={null}
        progress={{ query: 'Acme', name: 'Acme', sector: null, resolved: true, found: false, reviewed: false }}
        execution={{
          status: 'dead_letter', acceptedAt: '2026-07-15T12:00:00Z', attempts: 3, maxAttempts: 3,
          error: 'Execution failed after all retry attempts.',
        }}
        onRetryJob={retry}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Retry job' }));
    expect(retry).toHaveBeenCalledTimes(1);
  });
});
