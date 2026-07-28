import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import LookupReadyNotice from '../LookupReadyNotice';

describe('LookupReadyNotice', () => {
  it('presents a completed memo as an inline Dispatch handoff', () => {
    render(
      <LookupReadyNotice
        name="Aethria"
        recommendation="INVEST"
        onOpen={() => undefined}
        onDismiss={() => undefined}
      />,
    );

    expect(screen.getByRole('status')).toHaveTextContent('Memo ready');
    expect(screen.getByText('Aethria')).toBeInTheDocument();
    expect(screen.getByLabelText('INVEST')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Open memo →' })).toBeInTheDocument();
    expect(screen.getByRole('status').querySelector('[aria-hidden="true"]')).toHaveClass('bg-oxford', 'signal-dot-breathe');
  });

  it('opens and dismisses through explicit controls', () => {
    const onOpen = vi.fn();
    const onDismiss = vi.fn();
    render(
      <LookupReadyNotice
        name="Aethria"
        onOpen={onOpen}
        onDismiss={onDismiss}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Open memo →' }));
    fireEvent.click(screen.getByRole('button', { name: 'Dismiss memo ready notification' }));

    expect(onOpen).toHaveBeenCalledOnce();
    expect(onDismiss).toHaveBeenCalledOnce();
  });
});
