import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { createDefaultFundConfiguration, validateWeights } from '../../lib/fundConfiguration';
import CompactPolicy, { CompactThesis } from '../CompactSettings';

const options = { stages: ['Pre-seed', 'Seed', 'Series A'], geographies: ['US', 'Europe'], sectors: ['AI', 'Fintech'] };

function thesisDraft() {
  const draft = createDefaultFundConfiguration();
  return { ...draft, mandate: { ...draft.mandate, preferredStages: ['Seed'], sectors: ['AI', 'Fintech', 'Devtools'] } };
}

describe('CompactThesis', () => {
  it('edits text fields in place through the same mandate handler', () => {
    const updateMandate = vi.fn();
    render(<CompactThesis draft={thesisDraft()} updateMandate={updateMandate} options={options} liveThesis="Not published" />);

    fireEvent.change(screen.getByLabelText('Fund name'), { target: { value: 'Northwind' } });

    expect(updateMandate).toHaveBeenCalledWith('fundName', 'Northwind');
  });

  it('shows every option as a pill and toggles one directly, with no collapsed step', () => {
    const updateMandate = vi.fn();
    render(<CompactThesis draft={thesisDraft()} updateMandate={updateMandate} options={options} liveThesis="Not published" />);

    expect(screen.getByRole('button', { name: 'Seed' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('button', { name: 'Pre-seed' })).toHaveAttribute('aria-pressed', 'false');

    fireEvent.click(screen.getByRole('button', { name: 'Pre-seed' }));

    expect(updateMandate).toHaveBeenCalledWith('preferredStages', ['Seed', 'Pre-seed']);
  });

  it('removes a selected option when its pill is pressed again', () => {
    const updateMandate = vi.fn();
    render(<CompactThesis draft={thesisDraft()} updateMandate={updateMandate} options={options} liveThesis="Not published" />);

    fireEvent.click(screen.getByRole('button', { name: 'Seed' }));

    expect(updateMandate).toHaveBeenCalledWith('preferredStages', []);
  });

  it('keeps the Identity / Where / What / Economics grouping, with thesis as the first scroll target', () => {
    render(<CompactThesis draft={thesisDraft()} updateMandate={vi.fn()} options={options} liveThesis="Not published" />);

    const titles = screen.getAllByRole('heading', { level: 2 }).map((heading) => heading.textContent);
    expect(titles).toEqual([
      'Identity',
      'Where to invest',
      'What to invest in',
      'Economics',
      'Proof required',
      'Thesis narrative',
      'Version',
    ]);
    expect(document.getElementById('thesis')).toContainElement(screen.getByLabelText('Fund name'));
  });

  it('keeps the version section (a scroll and attention target) with draft and live thesis', () => {
    render(<CompactThesis draft={thesisDraft()} updateMandate={vi.fn()} options={options} liveThesis="Fund Thesis v3" />);

    expect(document.getElementById('version')).not.toBeNull();
    expect(screen.getByText('Fund Thesis v3')).toBeInTheDocument();
  });
});

describe('CompactPolicy', () => {
  function renderPolicy(overrides: Partial<React.ComponentProps<typeof CompactPolicy>> = {}) {
    const draft = createDefaultFundConfiguration();
    const handlers = {
      updateDraft: vi.fn(),
      updateThreshold: vi.fn(),
      updateRisk: vi.fn(),
      updateMemo: vi.fn(),
      setWeight: vi.fn(),
    };
    render(
      <CompactPolicy
        draft={draft}
        weightValidation={validateWeights(draft.scoringWeights)}
        bandErrors={[]}
        {...handlers}
        {...overrides}
      />,
    );
    return { draft, ...handlers };
  }

  it('renders the decision ladder so score bands stay editable', () => {
    renderPolicy();

    expect(screen.getByLabelText('Auto-pass threshold')).toBeInTheDocument();
    expect(screen.getByLabelText('Invest starts at')).toBeInTheDocument();
  });

  it('routes the segmented sensitivity switch through updateRisk', () => {
    const { updateRisk } = renderPolicy();

    fireEvent.click(screen.getByRole('radio', { name: 'Aggressive' }));

    expect(updateRisk).toHaveBeenCalledWith('sensitivity', 'aggressive');
  });

  it('steps a weight through setWeight', () => {
    const { draft, setWeight } = renderPolicy();
    const first = draft.scoringWeights[0];

    fireEvent.click(screen.getByRole('button', { name: `Increase ${first.label} weight` }));

    expect(setWeight).toHaveBeenCalledWith(first.key, first.weight + 1);
  });

  it('shows the invalid weight total and band errors instead of hiding them', () => {
    renderPolicy({ weightValidation: { valid: false, total: 97 }, bandErrors: ['Bands overlap'] });

    expect(screen.getByText('97%')).toBeInTheDocument();
    expect(screen.getByText('Bands overlap')).toBeInTheDocument();
  });

  it('flips a switch through updateRisk', () => {
    const { draft, updateRisk } = renderPolicy();

    fireEvent.click(screen.getByRole('switch', { name: 'Require acknowledgement before ruling' }));

    expect(updateRisk).toHaveBeenCalledWith('requireAcknowledgement', !draft.risk.requireAcknowledgement);
  });
});
