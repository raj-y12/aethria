import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

const appFrameSource = readFileSync(resolve(import.meta.dirname, '../src/components/AppFrame.tsx'), 'utf8');
const flowPageSource = readFileSync(resolve(import.meta.dirname, '../src/pages/FlowPage.tsx'), 'utf8');
const workGridSource = readFileSync(resolve(import.meta.dirname, '../src/components/WorkGrid.tsx'), 'utf8');

describe('Home to Flow entrance choreography', () => {
  it('runs the full chrome entrance before releasing the existing Flow stagger', () => {
    expect(appFrameSource).toContain('workspaceChromeReady: boolean;');
    expect(appFrameSource).toContain('const enteringFullChrome =');
    expect(appFrameSource).toContain('onAnimationComplete={completeWorkspaceChromeEntrance}');
    expect(appFrameSource).toContain('layout="position"');
    expect(appFrameSource).not.toContain('chromeModeChanged');
    expect(appFrameSource).toContain('const showSpine = !bareChrome && !dispatch.commandBarOpen;');
    expect(appFrameSource).toContain('const showMobileChrome = !isDesktop && !bareChrome && !dispatch.commandBarOpen;');
    expect(appFrameSource).toContain("exit={reduceMotion ? { opacity: 0 } : { opacity: 0, y: 10 }}");
    expect(appFrameSource).not.toContain('dispatchExitPending');
    expect(appFrameSource).not.toContain('dispatchTransitionActive');
    expect(appFrameSource).not.toContain('onExitComplete={completeDispatchExit}');
    expect(flowPageSource).toContain('workspaceChromeReady');
    expect(flowPageSource).toContain('entranceReady={workspaceChromeReady}');
    expect(workGridSource).toContain('entranceReady?: boolean;');
    expect(workGridSource).toContain("animate={reduceMotion || entranceReady ? 'visible' : 'hidden'}");
    expect(workGridSource).toContain('staggerChildren: 0.026');
    expect(workGridSource).not.toContain('autoSelectReady');
  });

  it('starts one light row cascade after chrome, without a second page entrance', () => {
    expect(flowPageSource).not.toContain('page-transition-enter');
    expect(flowPageSource).toContain('entranceReady={workspaceChromeReady}');
    expect(workGridSource).toContain("animate={reduceMotion || entranceReady ? 'visible' : 'hidden'}");
    expect(workGridSource).toContain('staggerChildren: 0.026');
    expect(workGridSource).toContain("translateY(3px)");
  });

  it('reveals the first desktop memo only after the WorkGrid stagger completes', () => {
    expect(flowPageSource).toContain('const [selectedStartup, setSelectedStartup] = useState<Startup | null>(null);');
    expect(flowPageSource).toContain("const openId = searchParams.get('open');");
    expect(flowPageSource).toContain('onStartupClick={handleStartupClick}');
    expect(flowPageSource).toContain('const handleGridEntranceComplete = useCallback((startup: Startup) => {');
    expect(flowPageSource).toContain('setSelectedStartup((current) => current ?? startup);');
    expect(flowPageSource).toContain('onEntranceComplete={isDesktop ? handleGridEntranceComplete : undefined}');
    expect(workGridSource).toContain('onEntranceComplete?: (startup: Startup) => void;');
    expect(workGridSource).toContain('onAnimationComplete={completeEntrance}');
    expect(workGridSource).toContain('onEntranceComplete?.(first.startup);');
    expect(flowPageSource).not.toContain('INITIAL_MEMO_DELAY_MS');
    expect(flowPageSource).not.toContain('setTimeout(');
  });
});
