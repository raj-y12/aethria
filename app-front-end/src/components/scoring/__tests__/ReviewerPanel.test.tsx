import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import ReviewerPanel from '../ReviewerPanel';

describe('ReviewerPanel', () => {
  it('renders nothing when there are no rows', () => {
    const { container } = render(
      <ReviewerPanel rows={[]} consensus={{ min: null, max: null, spread: null, split: false }} />
    );
    expect(container).toBeEmptyDOMElement();
  });

  it('flags a split panel instead of the quiet "Reviewer panel" label', () => {
    render(
      <ReviewerPanel
        rows={[{ key: 'DefaultReviewer', name: 'Default', score: 5 }]}
        consensus={{ min: 4, max: 6, spread: 2, split: true, verdict: 'MEDIUM' }}
      />
    );
    expect(screen.getByText('Reviewers split')).toBeInTheDocument();
    expect(screen.queryByText('Reviewer panel')).not.toBeInTheDocument();
  });

  it('uses the quiet label and no conviction-diverges hint when aligned', () => {
    render(
      <ReviewerPanel
        rows={[{ key: 'DefaultReviewer', name: 'Default', score: 5 }]}
        consensus={{ min: 5, max: 5, spread: 0, split: false }}
      />
    );
    expect(screen.getByText('Reviewer panel')).toBeInTheDocument();
    expect(screen.queryByText(/conviction diverges/)).not.toBeInTheDocument();
  });

  it('shows the conviction-diverges hint and spread line when spread >= 2', () => {
    render(
      <ReviewerPanel
        rows={[
          { key: 'SkepticalReviewer', name: 'Skeptical', score: 4 },
          { key: 'OpportunistReviewer', name: 'Opportunist', score: 6 },
        ]}
        consensus={{ min: 4, max: 6, spread: 2, split: true, verdict: 'MEDIUM' }}
      />
    );
    expect(screen.getByText(/4\.0.*6\.0.*spread/)).toBeInTheDocument();
    expect(screen.getByText(/conviction diverges/)).toBeInTheDocument();
  });

  it('renders data coverage on a row when supplied', () => {
    render(
      <ReviewerPanel
        rows={[{ key: 'DefaultReviewer', name: 'Default', score: 7, coverage: 0.8 }]}
        consensus={{ min: 7, max: 7, spread: 0, split: false }}
      />
    );
    expect(screen.getByText('80% data coverage')).toBeInTheDocument();
  });

  it('omits data coverage when not supplied, without erroring', () => {
    render(
      <ReviewerPanel
        rows={[{ key: 'DefaultReviewer', name: 'Default', score: 7 }]}
        consensus={{ min: 7, max: 7, spread: 0, split: false }}
      />
    );
    expect(screen.queryByText(/% data coverage/)).not.toBeInTheDocument();
  });

  it('names each persona\'s prompted posture as a tooltip on its row', () => {
    render(
      <ReviewerPanel
        rows={[{ key: 'SkepticalReviewer', name: 'Skeptical', score: 5 }]}
        consensus={{ min: 5, max: 5, spread: 0, split: false }}
      />
    );
    expect(screen.getByText('Skeptical').getAttribute('title')).toMatch(/assume the worst/);
  });

  it('discloses that the panel is one model over shared evidence, not independent reviews', () => {
    render(
      <ReviewerPanel
        rows={[{ key: 'DefaultReviewer', name: 'Default', score: 5 }]}
        consensus={{ min: 5, max: 5, spread: 0, split: false }}
      />
    );
    expect(
      screen.getByText('One model, one evidence packet, three prompted postures — not independent reviews.')
    ).toBeInTheDocument();
  });
});
