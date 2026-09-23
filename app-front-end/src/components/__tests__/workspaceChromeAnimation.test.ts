// Vitest provides Node's filesystem APIs at runtime; the app's browser build has no Node typings.
// @ts-expect-error Node-only test helper.
import { readFileSync } from 'node:fs';
// @ts-expect-error Node-only test helper.
import { resolve } from 'node:path';
import postcss from 'postcss';
import { describe, expect, it } from 'vitest';

declare const process: { cwd(): string };

describe('workspace chrome animation', () => {
  it('animates on initial load while keeping one presence key across workspace routes', async () => {
    const appFrame = (await import('../AppFrame')) as typeof import('../AppFrame') & {
      createWorkspaceChromePresence?: (surface: 'dock' | 'mobile') => unknown;
    };

    expect(appFrame.createWorkspaceChromePresence).toBeTypeOf('function');
    expect(appFrame.createWorkspaceChromePresence?.('dock')).toEqual({
      initial: true,
      key: 'workspace-dock',
    });
    expect(appFrame.createWorkspaceChromePresence?.('mobile')).toEqual({
      initial: true,
      key: 'workspace-mobile',
    });
  });

  it('slides the bottom workspace dock fully off-screen without fading it into a flash', async () => {
    const appFrame = (await import('../AppFrame')) as typeof import('../AppFrame') & {
      createWorkspaceDockMotion?: (reduceMotion: boolean) => unknown;
    };

    expect(appFrame.createWorkspaceDockMotion).toBeTypeOf('function');
    expect(appFrame.createWorkspaceDockMotion?.(false)).toEqual({
      initial: { '--workspace-chrome-y': '64px' },
      animate: { '--workspace-chrome-y': '0px' },
      exit: {
        '--workspace-chrome-y': '64px',
        transition: { duration: 0.5, ease: [0.77, 0, 0.175, 1] },
      },
      transition: { duration: 0.5, ease: [0.32, 0.72, 0, 1] },
    });
  });

  it('removes dock travel when reduced motion is requested', async () => {
    const appFrame = (await import('../AppFrame')) as typeof import('../AppFrame') & {
      createWorkspaceDockMotion?: (reduceMotion: boolean) => unknown;
    };

    expect(appFrame.createWorkspaceDockMotion?.(true)).toEqual({
      initial: { opacity: 1, '--workspace-chrome-y': '0px' },
      animate: { opacity: 1, '--workspace-chrome-y': '0px' },
      exit: { opacity: 0, '--workspace-chrome-y': '0px' },
      transition: { duration: 0 },
    });
  });

  it.each([
    ['Home', '.aethria-frame--home', '.aethria-spine'],
    ['Settings', '.aethria-frame--settings', '.aethria-spine'],
    ['Home on mobile', '.aethria-frame--home', '.aethria-mobile-header'],
    ['Settings on mobile', '.aethria-frame--settings', '.aethria-mobile-header'],
  ])('keeps the workspace dock renderable while Motion exits to %s', (_route, frame, chrome) => {
    const appStyles = readFileSync(resolve(process.cwd(), 'src/index.css'), 'utf8');
    const hidingSelectors: string[] = [];
    postcss.parse(appStyles).walkRules((rule) => {
      const hidesExitingSpine = rule.nodes.some(
        (node) => node.type === 'decl' && node.prop === 'display' && node.value === 'none',
      );
      if (
        hidesExitingSpine &&
        rule.selectors.some((selector) => selector.trim() === `${frame} ${chrome}`)
      ) {
        hidingSelectors.push(rule.selector);
      }
    });

    expect(hidingSelectors).toEqual([]);
  });
});
