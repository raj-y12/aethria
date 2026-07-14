import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import DispatchCommandBar from '../DispatchCommandBar';
import type { LookupCandidate } from '../../api/startups';

const candidates: LookupCandidate[] = [
  {
    name: 'Lyra Systems',
    website: 'https://lyra.example',
    description: 'Developer infrastructure for modern teams.',
    confidence: 0.92,
    source_badges: ['domain'],
  },
  {
    name: 'Lyra Health',
    website: 'https://lyrahealth.example',
    description: 'Care delivery platform.',
    confidence: 0.71,
    source_badges: ['domain'],
  },
];

describe('DispatchCommandBar active lookup', () => {
  it('widens the unresolved identity dossier while preserving its region', () => {
    vi.stubGlobal('matchMedia', () => ({
      matches: false,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
    }));
    const { container } = render(
      <DispatchCommandBar
        open
        onClose={() => undefined}
        input="Lyra"
        setInput={() => undefined}
        onSubmit={() => undefined}
        isBusy={false}
        message="Confirm the exact company."
        lookupPhase="Scouting"
        progress={{ query: 'Lyra', name: null, sector: null, resolved: false, found: false, reviewed: false }}
        candidates={candidates}
        onPickCandidate={() => undefined}
        onRefineWebsite={() => undefined}
      />,
    );
    expect(screen.getByRole('region', { name: 'Choose the company you meant' })).toBeInTheDocument();
    expect(container.querySelector('.max-w-4xl')).not.toBeNull();
  });

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
