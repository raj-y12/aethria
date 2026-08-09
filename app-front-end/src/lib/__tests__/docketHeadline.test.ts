import { describe, expect, it } from 'vitest';
import { docketHeadline } from '../docketHeadline';

describe('docketHeadline', () => {
  it('claims urgency only for the escalated view', () => {
    expect(docketHeadline('ESCALATED', { shown: 3, needRuling: 3 })).toEqual({
      eyebrow: 'Awaiting your ruling · 3 matters',
      urgent: true,
    });
    expect(docketHeadline('NEW', { shown: 3, needRuling: 0 }).urgent).toBe(false);
    expect(docketHeadline('STALE', { shown: 3, needRuling: 0 }).urgent).toBe(false);
  });

  it('agrees with the rows on screen, not the pipeline total', () => {
    // The escalated view shows 2 rows; the kicker must say 2, never 9.
    expect(docketHeadline('ESCALATED', { shown: 2, needRuling: 9 }).eyebrow).toBe(
      'Awaiting your ruling · 2 matters',
    );
  });

  it('singularises', () => {
    expect(docketHeadline('ESCALATED', { shown: 1, needRuling: 1 }).eyebrow).toBe(
      'Awaiting your ruling · 1 matter',
    );
    expect(docketHeadline('NEW', { shown: 1, needRuling: 0 }).eyebrow).toBe(
      'New since you left · 1 company',
    );
    expect(docketHeadline('STALE', { shown: 1, needRuling: 0 }).eyebrow).toBe('Gone quiet · 1 matter');
  });

  it('lets a waiting ruling outrank the open count', () => {
    const ruling = docketHeadline('PRIORITY', { shown: 34, needRuling: 3 });
    expect(ruling.eyebrow).toBe('Awaiting your ruling · 3 matters');
    expect(ruling.urgent).toBe(true);

    const calm = docketHeadline('PRIORITY', { shown: 34, needRuling: 0 });
    expect(calm.eyebrow).toBe('On the desk · 34 matters');
    expect(calm.urgent).toBe(false);
  });

  it('names an empty view instead of counting zero', () => {
    expect(docketHeadline('ESCALATED', { shown: 0, needRuling: 0 }).eyebrow).toBe(
      'Awaiting your ruling · none',
    );
    expect(docketHeadline('NEW', { shown: 0, needRuling: 0 }).eyebrow).toBe('New since you left · none');
    expect(docketHeadline('ALL', { shown: 0, needRuling: 0 }).eyebrow).toBe('On the desk · none');
  });
});
