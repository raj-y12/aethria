import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

const appFrameSource = readFileSync(resolve(import.meta.dirname, '../src/components/AppFrame.tsx'), 'utf8');
const flowPageSource = readFileSync(resolve(import.meta.dirname, '../src/pages/FlowPage.tsx'), 'utf8');
const workGridSource = readFileSync(resolve(import.meta.dirname, '../src/components/WorkGrid.tsx'), 'utf8');

describe('Home to Flow entrance choreography', () => {
  it('restores synchronized workspace motion and sequences chrome after Dispatch exits', () => {
    expect(appFrameSource).toContain('layout="position"');
    expect(appFrameSource).toContain('transition={chromeTransition}');
    expect(appFrameSource).toContain('dispatchTransitionActive');
    expect(appFrameSource).toContain('onExitComplete={completeDispatchExit}');
    expect(appFrameSource).toContain("exit={reduceMotion ? { opacity: 0 } : { opacity: 0, y: -10 }}");
  });

  it('starts one light row cascade immediately, without a second page entrance', () => {
    expect(flowPageSource).not.toContain('page-transition-enter');
    expect(flowPageSource).not.toContain('entranceReady=');
    expect(workGridSource).toContain("animate={reduceMotion ? undefined : 'visible'}");
    expect(workGridSource).toContain('staggerChildren: 0.026');
    expect(workGridSource).toContain("translateY(3px)");
  });

  it('selects the initial case before paint so rows never reflow mid-cascade', () => {
    expect(workGridSource).toContain('useLayoutEffect(() => {');
    expect(workGridSource).not.toContain('INITIAL_MEMO_DELAY_MS');
    expect(workGridSource).not.toContain('autoSelectReady');
    expect(workGridSource).not.toContain('entranceReady');
  });
});
