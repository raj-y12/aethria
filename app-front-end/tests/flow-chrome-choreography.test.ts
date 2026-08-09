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

  /* The memo is an overlay on every viewport, so Flow opens on the docket with
   * nothing selected. Auto-revealing the first company would raise a modal over
   * an operator who never asked for one — the old auto-select only made sense
   * when the memo was a second column that would otherwise sit empty. A memo now
   * opens on a deliberate act: a row click, or an ?open= deep link. */
  it('opens on the docket and raises a memo only on a deliberate act', () => {
    expect(flowPageSource).toContain('const [selectedStartup, setSelectedStartup] = useState<Startup | null>(null);');
    expect(flowPageSource).toContain("const openId = searchParams.get('open');");
    expect(flowPageSource).toContain('onStartupClick={handleStartupClick}');
    expect(flowPageSource).not.toContain('handleGridEntranceComplete');
    expect(flowPageSource).not.toContain('onEntranceComplete');
    expect(workGridSource).not.toContain('onEntranceComplete');
    expect(flowPageSource).not.toContain('INITIAL_MEMO_DELAY_MS');
    expect(flowPageSource).not.toContain('setTimeout(');
  });

  /* Desktop: the docket gives up its basis and settles left while the memo rises
   * beside it. Driving the push through flex-basis rather than a static grid (or
   * a `layout` transform) keeps the type from scaling during the move. Below lg
   * there is no room for two columns, so the memo takes the screen as a modal. */
  it('pushes the docket left and raises the memo beside it on desktop', () => {
    expect(flowPageSource).not.toContain('aethria-flow-grid');
    expect(flowPageSource).toContain('const splitOpen = isDesktop && Boolean(selectedStartup);');
    expect(flowPageSource).toContain('const useModal = Boolean(selectedStartup) && !isDesktop;');
    expect(flowPageSource).toContain("animate={{ flexBasis: splitOpen ? '38%' : '100%' }}");
    expect(flowPageSource).toContain('<InvestmentMemoContent');
    expect(flowPageSource).toContain('<InvestmentMemo');
  });

  /* The docket keeps its brackets in both states, so it still reads as a framed
   * surface once it settles left rather than becoming a bare column. That needs
   * the wide gutter in both states too — the brackets sit outside the body.
   * The frame is pinned to the column and the matters scroll inside it, so the
   * brackets, the headline and the tally all stay put. */
  it('keeps the docket framed in both states, with the list scrolling inside', () => {
    expect(flowPageSource).toContain('focus-frame focus-frame--docket mt-phi-5 mb-phi-5 flex min-h-0 flex-1 flex-col');
    // The column itself must not scroll, or the frame would scroll away with it.
    expect(flowPageSource).toContain('flex-col overflow-hidden');
    expect(flowPageSource).toContain('min-h-0 flex-1 overflow-y-auto overscroll-contain');
  });

  /* Flow sits on the same room measure as Portfolio and Fund — the split happens
   * inside --room-max rather than across the whole viewport. The docket brackets
   * use the tucked variant so they fit the room's px-phi-5 gutter. */
  it('lays the room out on the shared workspace measure', () => {
    expect(flowPageSource).toContain('${workspaceLayout.shell}');
    expect(flowPageSource).toContain('focus-frame--docket');
    const css = readFileSync(resolve(import.meta.dirname, '../src/index.css'), 'utf8');
    expect(css).toContain('.focus-frame--docket::before');
  });
});
