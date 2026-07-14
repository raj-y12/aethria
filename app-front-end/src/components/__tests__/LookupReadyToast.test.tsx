import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import LookupReadyToast from '../LookupReadyToast';

describe('LookupReadyToast', () => {
  it('presents a completed memo as an Oxford decision alert', () => {
    render(
      <LookupReadyToast
        name="Aethria"
        recommendation="INVEST"
        onOpen={() => undefined}
        onDismiss={() => undefined}
      />,
    );

    expect(screen.getByRole('status')).toHaveTextContent('Memo ready');
    expect(screen.getByText('Aethria')).toBeInTheDocument();
    expect(screen.getByLabelText('INVEST')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Open memo' })).toBeInTheDocument();
    expect(screen.getByRole('status').firstElementChild).toHaveClass('border');
  });

  it('opens and dismisses through explicit controls', () => {
    const onOpen = vi.fn();
    const onDismiss = vi.fn();
    render(
      <LookupReadyToast
        name="Aethria"
        onOpen={onOpen}
        onDismiss={onDismiss}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Open memo' }));
    fireEvent.click(screen.getByRole('button', { name: 'Dismiss memo ready notification' }));

    expect(onOpen).toHaveBeenCalledOnce();
    expect(onDismiss).toHaveBeenCalledOnce();
  });
});
