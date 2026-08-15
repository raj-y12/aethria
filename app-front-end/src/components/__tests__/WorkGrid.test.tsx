import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { describe, expect, it, vi } from 'vitest';
import type { Startup } from '../../types/startup';
import WorkGrid from '../WorkGrid';

const startup: Startup = {
  id: 'keyboard-docket-fixture',
  scout: {
    id: 'keyboard-docket-fixture',
    scout_type: 'market_driven',
    name: 'Keyboard Docket Co',
    one_line: 'A fixture used to verify docket memo activation.',
    sector: 'Enterprise software',
    why_now: 'The test needs a renderable queue row.',
    confidence: 0.7,
  },
  timestamps: { discovered_at: '2026-06-01T09:00:00Z' },
};

describe('WorkGrid', () => {
  it('opens the same memo from click, Enter, and Space on a focused docket row', () => {
    const onStartupClick = vi.fn();

    render(
      <MemoryRouter>
        <WorkGrid
          startups={[startup]}
          onStartupClick={onStartupClick}
          queueView="PRIORITY"
          onQueueViewChange={vi.fn()}
        />
      </MemoryRouter>,
    );

    const docketRow = screen.getByRole('button', { name: /Keyboard Docket Co/ });

    fireEvent.click(docketRow);
    expect(onStartupClick).toHaveBeenCalledTimes(1);
    expect(onStartupClick).toHaveBeenLastCalledWith(startup);

    docketRow.focus();
    expect(docketRow).toHaveFocus();

    fireEvent.keyDown(docketRow, { key: 'Enter' });
    expect(onStartupClick).toHaveBeenCalledTimes(2);
    expect(onStartupClick).toHaveBeenLastCalledWith(startup);

    fireEvent.keyDown(docketRow, { key: ' ' });
    expect(onStartupClick).toHaveBeenCalledTimes(3);
    expect(onStartupClick).toHaveBeenLastCalledWith(startup);
  });

  it('replaces a selected legacy recommendation when its canonical decision is unavailable', () => {
    const unavailableStartup: Startup = {
      ...startup,
      partner: {
        recommendation: 'PASS',
        human_review_required: true,
      },
      review: { overall_score: 2.5 },
    };
    const props = {
      startups: [unavailableStartup],
      onStartupClick: vi.fn(),
      selectedId: unavailableStartup.id,
      selectedDecisionStatus: 'unavailable',
      queueView: 'PRIORITY',
      onQueueViewChange: vi.fn(),
    };

    render(
      <MemoryRouter>
        {/** The status prop is the behavior under test and is introduced by the fix. */}
        <WorkGrid {...(props as unknown as React.ComponentProps<typeof WorkGrid>)} />
      </MemoryRouter>,
    );

    const docketRow = screen.getByRole('button', { name: /Keyboard Docket Co/ });
    expect(docketRow).toHaveTextContent('Decision unavailable');
    expect(docketRow).not.toHaveTextContent('PASS');
    expect(docketRow).not.toHaveTextContent('25');
  });
});
