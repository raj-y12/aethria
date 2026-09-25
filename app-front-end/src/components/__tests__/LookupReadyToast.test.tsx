import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import LookupReadyNotice from '../LookupReadyNotice';

describe('LookupReadyNotice', () => {
  it('presents a completed memo as a compact clickable Dispatch notice', () => {
    render(
      <LookupReadyNotice
        name="Aethria"
        recommendation="INVEST"
        onOpen={() => undefined}
      />,
    );

    expect(screen.getByRole('status')).toBeInTheDocument();
    expect(screen.getByText('Aethria')).toBeInTheDocument();
    expect(screen.getByText('INVEST')).toHaveClass('bg-oxford', 'text-paper');
    expect(screen.getByRole('button', { name: 'Open memo for Aethria, INVEST' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /dismiss/i })).not.toBeInTheDocument();
  });

  it('opens the memo when the notice is clicked', () => {
    const onOpen = vi.fn();
    render(
      <LookupReadyNotice
        name="Aethria"
        onOpen={onOpen}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Open memo for Aethria' }));

    expect(onOpen).toHaveBeenCalledOnce();
  });

  it('uses the displayed recommendation label in the button accessible name', () => {
    render(
      <LookupReadyNotice
        name="Aethria"
        recommendation="INVEST"
        recommendationLabel="More diligence"
        onOpen={() => undefined}
      />,
    );

    expect(screen.getByText('More diligence')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Open memo for Aethria, More diligence' })).toBeInTheDocument();
  });
});
