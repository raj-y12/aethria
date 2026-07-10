import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import type { Startup } from '../../../types/startup';
import { buildMemoTags } from '../memoContentHelpers';
import MemoTags from '../MemoTags';

function makeStartup(scout: Partial<Startup['scout']>): Startup {
  return {
    id: 'tag-fixture',
    scout: {
      id: 'tag-fixture',
      scout_type: 'market_driven',
      name: 'Tag Fixture Co',
      one_line: 'Fixture one-liner',
      sector: 'Industrial AI',
      why_now: 'Fixture timing.',
      confidence: 0.7,
      ...scout,
    },
    timestamps: { discovered_at: '2026-06-01T09:00:00Z', first_seen_at: '2026-06-01T09:00:00Z' },
  };
}

describe('buildMemoTags', () => {
  it('orders sector, then stage, then lookup origin', () => {
    const tags = buildMemoTags(
      makeStartup({ sector: 'Robotics', funding_stage: 'Seed', origin_type: 'on_demand_lookup' }),
    );
    expect(tags).toEqual([
      { label: 'ROBOTICS', kind: 'sector' },
      { label: 'SEED', kind: 'stage' },
      { label: 'LOOKUP', kind: 'origin' },
    ]);
  });

  it('falls back to scout type for stage and humanises underscores', () => {
    const tags = buildMemoTags(makeStartup({ funding_stage: undefined }));
    expect(tags.map((tag) => tag.label)).toEqual(['INDUSTRIAL AI', 'MARKET DRIVEN']);
  });

  it('drops empties and duplicate labels', () => {
    const tags = buildMemoTags(makeStartup({ sector: 'Seed', funding_stage: 'Seed' }));
    expect(tags).toEqual([{ label: 'SEED', kind: 'sector' }]);
  });

  it('omits LOOKUP for scout-originated startups', () => {
    const tags = buildMemoTags(makeStartup({ origin_type: 'scout', funding_stage: 'Seed' }));
    expect(tags.some((tag) => tag.kind === 'origin')).toBe(false);
  });
});

describe('MemoTags', () => {
  it('renders each tag as a list item', () => {
    render(<MemoTags startup={makeStartup({ funding_stage: 'Seed' })} />);
    const list = screen.getByRole('list', { name: 'Company classification' });
    expect(list).toBeInTheDocument();
    expect(screen.getByText('INDUSTRIAL AI')).toBeInTheDocument();
    expect(screen.getByText('SEED')).toBeInTheDocument();
  });

  it('renders nothing when there are no tags', () => {
    const { container } = render(
      <MemoTags startup={makeStartup({ sector: '', funding_stage: '', scout_type: '' })} />,
    );
    expect(container).toBeEmptyDOMElement();
  });
});
