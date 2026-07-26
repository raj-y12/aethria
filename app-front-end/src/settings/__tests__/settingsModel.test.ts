import { describe, expect, it } from 'vitest';
import {
  sectionForDeploymentError,
  SETTINGS_GROUPS,
  SETTINGS_SECTIONS,
} from '../settingsModel';

describe('settings persistence model', () => {
  it('defines truthful settings boundaries', () => {
    expect(SETTINGS_GROUPS.map((group) => group.label)).toEqual([
      'Fund thesis',
      'Decision policy',
      'Workspace runtime',
      'System',
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

describe('deployment error routing', () => {
  it.each([
    ['Scoring weights must total 100', 'weights'],
    ['Monitor threshold overlaps invest', 'thresholds'],
    ['Memo output is invalid', 'memo'],
    ['Risk ruling is incomplete', 'workflow'],
    ['Fund thesis is required', 'thesis'],
  ] as const)('routes %s to %s', (error, section) => {
    expect(sectionForDeploymentError(error)).toBe(section);
  });
});
