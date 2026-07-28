import { describe, expect, it } from 'vitest';

import { deriveWorkspaceChromeReady } from '../AppFrame';

/**
 * WorkGrid renders `initial='hidden'` and animates to visible only when this
 * gate is true, so a wrong `false` does not delay Flow's rows — it leaves them
 * at opacity 0 and they never appear. These cover each way into Flow.
 */
describe('workspace chrome readiness', () => {
  it('releases the cascade immediately when the spine is already up (Portfolio → Flow)', () => {
    // Both rooms are full chrome, so the spine never unmounts or re-animates:
    // AppFrame's layout effect does not re-run and the completion flag stays set.
    expect(
      deriveWorkspaceChromeReady({
        reduceMotion: false,
        previousChrome: 'full',
        chrome: 'full',
        chromeEntranceComplete: true,
      }),
    ).toBe(true);
  });

  it('holds the cascade while the spine enters from the front door (Home → Flow)', () => {
    expect(
      deriveWorkspaceChromeReady({
        reduceMotion: false,
        previousChrome: 'bare',
        chrome: 'full',
        chromeEntranceComplete: false,
      }),
    ).toBe(false);
  });

  it('releases it once that spine entrance reports complete', () => {
    // The layout effect has since written previousChrome back to 'full'.
    expect(
      deriveWorkspaceChromeReady({
        reduceMotion: false,
        previousChrome: 'full',
        chrome: 'full',
        chromeEntranceComplete: true,
      }),
    ).toBe(true);
  });

  it('never strands the rows when the entrance flag has not landed yet on a settled spine', () => {
    // Guards the failure mode: full→full must not depend on a stale completion
    // flag being re-set, because nothing would re-set it.
    expect(
      deriveWorkspaceChromeReady({
        reduceMotion: true,
        previousChrome: 'full',
        chrome: 'full',
        chromeEntranceComplete: false,
      }),
    ).toBe(true);
  });

  it('bypasses the gate entirely under reduced motion', () => {
    expect(
      deriveWorkspaceChromeReady({
        reduceMotion: true,
        previousChrome: 'bare',
        chrome: 'full',
        chromeEntranceComplete: false,
      }),
    ).toBe(true);
  });
});
