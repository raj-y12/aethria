import { fireEvent, render, screen, within } from '@testing-library/react';
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
        chips={[{ id: 'lookup-1', label: 'Acme', stage: 'Review', status: 'reviewing', active: true }]}
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
    expect(screen.queryByText(/Attempt \d+ of \d+/i)).not.toBeInTheDocument();
  });

  it('keeps multiple dispatches in a compact queue and labels their pipeline stages', () => {
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
          query: 'Aethria',
          name: 'Aethria',
          sector: 'AI',
          resolved: true,
          found: true,
          reviewed: false,
        }}
        chips={[
          { id: 'lookup-1', label: 'Aethria', stage: 'Review', status: 'reviewing', active: true },
          { id: 'lookup-2', label: 'Morrow', stage: 'Discover', status: 'scouting', active: false },
          { id: 'lookup-3', label: 'Kite', stage: 'Decide', status: 'decided', active: false },
        ]}
        onFocusChip={focus}
      />,
    );

    expect(screen.getByRole('region', { name: 'Active dispatches' })).toBeInTheDocument();
    const queue = screen.getByRole('region', { name: 'Active dispatches' });
    expect(within(queue).getByText('2 active')).toBeInTheDocument();
    expect(within(queue).getByText('Aethria')).toBeInTheDocument();
    expect(within(queue).getByText('Morrow')).toBeInTheDocument();
    expect(within(queue).getByText('Kite')).toBeInTheDocument();
    expect(within(queue).getByText('Review')).toBeInTheDocument();
    expect(within(queue).getByText('Discover')).toBeInTheDocument();
    expect(within(queue).getByText('Decide')).toBeInTheDocument();
    expect(screen.getByLabelText('Analysis progress')).toBeInTheDocument();
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

  it('carries earlier re-review notes forward instead of starting blank', () => {
    const submit = vi.fn();
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
        rerun={{ name: 'Acme', sector: 'AI', previousContext: 'Raised $2.1M pre-seed (unannounced).' }}
        onSubmitRerun={submit}
      />,
    );

    const textarea = screen.getByLabelText('Additional context') as HTMLTextAreaElement;
    expect(textarea.value).toBe('Raised $2.1M pre-seed (unannounced).');
    expect(screen.getByText(/Your earlier notes are below/)).toBeInTheDocument();
    fireEvent.change(textarea, { target: { value: 'Raised $2.1M pre-seed (unannounced). Pilot now live with two design partners.' } });
    fireEvent.click(screen.getByRole('button', { name: 'Review again →' }));
    expect(submit).toHaveBeenCalledWith('Raised $2.1M pre-seed (unannounced). Pilot now live with two design partners.');
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
