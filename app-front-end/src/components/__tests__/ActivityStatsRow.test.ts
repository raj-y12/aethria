import { describe, expect, it } from 'vitest';
import { activityStatsFromSummary } from '../ActivityStatsRow';

describe('activityStatsFromSummary', () => {
  it('does not present an all-zero response as an activity report', () => {
    expect(
      activityStatsFromSummary({
        found: 0,
        reviewed: 0,
        decided: 0,
        agent_decided: 0,
        human_reviewed: 0,
        open_in_progress: 3,
        escalations: 0,
      }),
    ).toEqual([]);
  });
});
