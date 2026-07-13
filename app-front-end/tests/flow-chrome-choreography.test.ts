import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

const appFrameSource = readFileSync(resolve(import.meta.dirname, '../src/components/AppFrame.tsx'), 'utf8');
const flowPageSource = readFileSync(resolve(import.meta.dirname, '../src/pages/FlowPage.tsx'), 'utf8');
const workGridSource = readFileSync(resolve(import.meta.dirname, '../src/components/WorkGrid.tsx'), 'utf8');

describe('Home to Flow entrance choreography', () => {
  it('lets AppFrame own an animation-completion readiness signal', () => {
    expect(appFrameSource).toContain('workspaceChromeReady');
    expect(appFrameSource).toContain('completeWorkspaceChromeEntrance');
    expect(appFrameSource).toContain('onAnimationComplete={completeWorkspaceChromeEntrance}');
  });

  it('holds the initial docket cascade until real chrome completion', () => {
    expect(flowPageSource).toContain('entranceReady={workspaceChromeReady}');
    expect(workGridSource).toContain("animate={reduceMotion || entranceReady ? 'visible' : 'hidden'}");
    expect(workGridSource).not.toContain('chromeSettled');
    expect(workGridSource).not.toContain('setChromeSettled');
  });

  it('starts memo auto-selection from the same readiness boundary', () => {
    expect(workGridSource).toContain('if (!entranceReady)');
    expect(workGridSource).toContain('[entranceReady, reduceMotion]');
  });
});
