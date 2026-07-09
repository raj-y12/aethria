/**
 * Poll-cadence selection for the deal-flow grid: only a proven-healthy SSE
 * stream may relax polling to the 30s safety net. Connecting/stale/closed
 * streams keep brisk 15s polling — independent of user idleness — so an
 * analyst waiting without touching the mouse never sees minute-scale lag.
 */
import { describe, expect, it } from 'vitest';
import { startupsPollInterval } from '../src/hooks/useSystemData';

describe('startupsPollInterval', () => {
  it('never polls while the tab is hidden', () => {
    expect(startupsPollInterval(false, true)).toBe(false);
    expect(startupsPollInterval(false, false)).toBe(false);
  });

  it('relaxes to the 30s safety net only when the stream is proven healthy', () => {
    expect(startupsPollInterval(true, true)).toBe(30_000);
  });

  it('polls briskly at 15s whenever the stream is not healthy', () => {
    // Covers connecting, stale, and closed — the hook collapses all three to
    // streamHealthy=false. Must stay <= 15s so a stale stream cannot cause
    // minute-scale staleness for an idle analyst.
    expect(startupsPollInterval(true, false)).toBe(15_000);
  });
});
