import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
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
});
