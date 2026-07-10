import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { Startup } from '../../../types/startup';
import MemoMasthead from '../MemoMasthead';

const startup: Startup = {
  id: 'masthead-fixture',
  scout: {
    id: 'masthead-fixture',
    scout_type: 'market_driven',
    name: 'Vantor Systems',
    one_line: 'Fixture one-liner',
    sector: 'Industrial AI',
    why_now: 'Fixture timing.',
    confidence: 0.7,
    funding_stage: 'Seed',
    location: 'Berlin',
  },
  timestamps: { discovered_at: '2026-06-01T09:00:00Z', first_seen_at: '2026-06-01T09:00:00Z' },
};

describe('MemoMasthead', () => {
  it('renders the action band with add-context, PDF, and close', async () => {
    const onAddContext = vi.fn();
    const onDownloadPDF = vi.fn();
    const onClose = vi.fn();
    render(
      <MemoMasthead
        startup={startup}
        onAddContext={onAddContext}
        onDownloadPDF={onDownloadPDF}
        onClose={onClose}
      />,
    );
    await userEvent.click(
      screen.getByRole('button', { name: 'Add context and re-review Vantor Systems' }),
    );
    await userEvent.click(screen.getByRole('button', { name: 'Download IC pack as PDF' }));
    await userEvent.click(screen.getByRole('button', { name: 'Close' }));
    expect(onAddContext).toHaveBeenCalledOnce();
    expect(onDownloadPDF).toHaveBeenCalledOnce();
    expect(onClose).toHaveBeenCalledOnce();
  });

  it('hides add-context in read-only view but keeps the PDF', () => {
    render(
      <MemoMasthead startup={startup} onAddContext={vi.fn()} onDownloadPDF={vi.fn()} readOnly />,
    );
    expect(screen.queryByRole('button', { name: /Add context/ })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Download IC pack as PDF' })).toBeInTheDocument();
  });

  it('renders the complete dossier identity when embedded or standalone', () => {
    const { container } = render(
      <MemoMasthead startup={startup} onAddContext={vi.fn()} onDownloadPDF={vi.fn()} />,
    );
    expect(screen.queryByRole('button', { name: 'Close' })).not.toBeInTheDocument();
    expect(screen.queryByText('Aethria / IC')).not.toBeInTheDocument();
    expect(screen.queryByText(/Dossier/i)).not.toBeInTheDocument();
    expect(screen.getByText('01 Jun 2026')).toBeInTheDocument();
    expect(container.querySelector('.memoMastheadFolio > time')).not.toBeNull();
    expect(container.querySelector('.memoMastheadFolio > .memoMastheadActions')).not.toBeNull();
    expect(screen.getByText('Berlin')).toBeInTheDocument();
    expect(screen.getByText('Fixture one-liner')).toBeInTheDocument();
    expect(screen.getByText('INDUSTRIAL AI')).toBeInTheDocument();
  });
});
