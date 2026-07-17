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
    expect(screen.getByText('Best match')).toBeInTheDocument();
    expect(screen.getByText('Strong identity match · Verified by Official site, LinkedIn, Press')).toBeInTheDocument();
    // A bare domain is never presented as verification.
    expect(screen.getByText('Likely identity match · Domain found — not verified')).toBeInTheDocument();
    expect(screen.queryByText(/Verified by Official domain candidate/)).not.toBeInTheDocument();
    expect(screen.queryByText(/%/)).not.toBeInTheDocument();
  });

  it('preserves selection and website refinement callbacks', () => {
    const onPick = vi.fn();
    const onRefine = vi.fn();
    render(<CandidatePicker candidates={candidates} onPick={onPick} onRefine={onRefine} />);
    fireEvent.click(screen.getByRole('button', { name: 'Use Lyra Health at lyrahealth.com' }));
    expect(onPick).toHaveBeenCalledWith(candidates[0]);
    fireEvent.click(screen.getByRole('button', { name: 'None of these — add a website' }));
    fireEvent.change(screen.getByLabelText('Company website'), { target: { value: 'other.example' } });
    fireEvent.click(screen.getByRole('button', { name: 'Resolve website' }));
    expect(onRefine).toHaveBeenCalledWith('other.example');
  });

  it('reports honestly when neither evidence nor a domain exists', () => {
    render(<CandidatePicker candidates={[{ ...candidates[0], website: '', source_badges: [] }]} onPick={() => undefined} onRefine={() => undefined} />);
    expect(screen.getByText('Strong identity match · No verification evidence')).toBeInTheDocument();
    expect(screen.getByText('Website not verified')).toBeInTheDocument();
  });
});
