import { describe, expect, it } from 'vitest';
import { SETTINGS_GROUPS, SETTINGS_SECTIONS } from '../settingsModel';

describe('settings persistence model', () => {
  it('defines the two truthful persistence groups', () => {
    expect(SETTINGS_GROUPS.map((group) => group.label)).toEqual([
      'Fund policy',
      'Live runtime',
    ]);
  });

  it('keeps desktop and mobile navigation in page order', () => {
    expect(SETTINGS_SECTIONS.map((section) => section.id)).toEqual([
      'thesis',
      'version',
      'thresholds',
      'sensitivity',
      'weights',
      'memo',
      'workflow',
      'budget',
      'system',
    ]);
  });
});
