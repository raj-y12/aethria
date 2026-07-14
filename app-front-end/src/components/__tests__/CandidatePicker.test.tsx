import { fireEvent, render, screen } from '@testing-library/react';
import { beforeAll, describe, expect, it, vi } from 'vitest';
import CandidatePicker from '../CandidatePicker';

const candidates = [
  {
    name: 'Lyra Health',
    website: 'https://lyrahealth.com',
    description: 'Workforce mental-health care platform for employers.',
    confidence: 0.91,
    source_badges: ['official', 'linkedin', 'news'],
  },
  {
    name: 'Lyra',
    website: 'https://lyra.ie',
    description: '',
    confidence: 0.63,
    source_badges: [],
  },
];

beforeAll(() => {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: (query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addEventListener: () => undefined,
      removeEventListener: () => undefined,
      addListener: () => undefined,
      removeListener: () => undefined,
      dispatchEvent: () => false,
    }),
  });
});

describe('CandidatePicker', () => {
  it('shows a decision-useful identity brief for every candidate', () => {
    render(<CandidatePicker candidates={candidates} onPick={() => undefined} onRefine={() => undefined} />);
    expect(screen.getByText('2 plausible identities')).toBeInTheDocument();
    expect(screen.getByText('Best match')).toBeInTheDocument();
    expect(screen.getByText('Strong identity match')).toBeInTheDocument();
    expect(screen.getByText('91%')).toBeInTheDocument();
    expect(screen.getByText('Official site')).toBeInTheDocument();
    expect(screen.getByText('LinkedIn')).toBeInTheDocument();
    expect(screen.getByText('Press')).toBeInTheDocument();
    expect(screen.getByText('No description was confirmed for this domain.')).toBeInTheDocument();
  });

  it('preserves selection and website refinement callbacks', () => {
    const onPick = vi.fn();
    const onRefine = vi.fn();
    render(<CandidatePicker candidates={candidates} onPick={onPick} onRefine={onRefine} />);
    fireEvent.click(screen.getByRole('button', { name: 'Use Lyra Health at lyrahealth.com' }));
    expect(onPick).toHaveBeenCalledWith(candidates[0]);
    fireEvent.click(screen.getByRole('button', { name: 'None of these companies' }));
    fireEvent.change(screen.getByLabelText('Company website'), { target: { value: 'other.example' } });
    fireEvent.click(screen.getByRole('button', { name: 'Resolve website' }));
    expect(onRefine).toHaveBeenCalledWith('other.example');
  });

  it('keeps the evidence rail responsive and gates hover affordances to fine pointers', () => {
    render(<CandidatePicker candidates={candidates} onPick={() => undefined} onRefine={() => undefined} />);
    const row = screen.getAllByRole('listitem')[0];
    const refineTrigger = screen.getByRole('button', { name: 'None of these companies' });

    expect(row).toHaveClass('grid-cols-1', 'sm:grid-cols-[minmax(3rem,.12fr)_minmax(0,1fr)_auto]');
    expect(row.className).toContain('pointer:fine');
    expect(refineTrigger.className).toContain('pointer:fine');
  });

  it('keeps long descriptions bounded for responsive rows', () => {
    render(<CandidatePicker candidates={[{ ...candidates[0], description: 'A very long company description that should remain readable without making each candidate row grow indefinitely.' }]} onPick={() => undefined} onRefine={() => undefined} />);
    const description = screen.getByText(/A very long company description/);
    expect(description).toHaveClass('line-clamp-3', 'max-h-[4.5rem]', 'overflow-hidden');
  });

  it('gives picker actions a short transform affordance with reduced-motion fallbacks', () => {
    render(<CandidatePicker candidates={candidates} onPick={() => undefined} onRefine={() => undefined} />);
    const refineTrigger = screen.getByRole('button', { name: 'None of these companies' });
    const expectedMotionClasses = ['duration-150', 'active:scale-[0.985]', 'motion-reduce:transition-none', 'motion-reduce:active:scale-100'];

    expectedMotionClasses.forEach((className) => expect(refineTrigger.className).toContain(className));

    expect(screen.getByRole('button', { name: 'Use Lyra Health at lyrahealth.com' }).className).toContain('motion-reduce:active:scale-100');
    fireEvent.click(refineTrigger);
    expect(screen.getByRole('button', { name: 'Resolve website' }).className).toContain('motion-reduce:active:scale-100');
  });
});
