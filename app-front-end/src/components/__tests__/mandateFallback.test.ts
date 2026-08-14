import { describe, expect, it } from 'vitest';
import { resolveMandateVersion } from '../AppFrame';

describe('resolveMandateVersion', () => {
  it('uses the canonical agents status when the summary request is unavailable', () => {
    expect(resolveMandateVersion(null, { active_thesis_version_id: 'v37' }, 37)).toEqual({
      id: 'v37',
      number: 37,
    });
  });

  it('prefers the complete thesis summary when both reads are present', () => {
    expect(
      resolveMandateVersion(
        { active_version_id: 'v38', active_version_number: 38 },
        { active_thesis_version_id: 'v37' },
        37,
      ),
    ).toEqual({ id: 'v38', number: 38 });
  });

  it('does not invent a mandate from settings alone', () => {
    expect(resolveMandateVersion(null, null, 37)).toEqual({ id: null, number: null });
  });
});
