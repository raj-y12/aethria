import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

const read = (p: string) => readFileSync(resolve(import.meta.dirname, '..', p), 'utf8');

const fundSource = read('src/pages/FundPage.tsx');
const portfolioSource = read('src/pages/PortfolioPage.tsx');
const settingsSource = read('src/settings/SettingsPage.tsx');
const homeSource = read('src/pages/HomePage.tsx');
const appCss = read('src/index.css');

/**
 * Rooms that arrive as a whole share one entrance, so navigating between them
 * feels like one system. Before this, Fund used the CSS class, Portfolio wrapped
 * its body in a Reveal, and Settings faded its reading column separately —
 * three timings for the same moment.
 *
 * Two rooms are deliberately NOT on it, and both are load-bearing exceptions:
 *   - Flow choreographs against the chrome entrance and then cascades its rows
 *     (see flow-chrome-choreography.test.ts, which forbids the class outright).
 *   - Home is the front door; its staggered briefing reveal IS the arrival, and
 *     a page fade over the top would compound with every Reveal beneath it.
 */
describe('page transitions', () => {
  it('gives every whole-arrival room the same entrance', () => {
    for (const [name, source] of [
      ['FundPage', fundSource],
      ['PortfolioPage', portfolioSource],
      ['SettingsPage', settingsSource],
    ] as const) {
      expect(source, `${name} should use the shared page entrance`).toContain('page-transition-enter');
    }
  });

  it('never stacks a second page-level entrance on top of it', () => {
    // Portfolio used to wrap its whole body in a Reveal as well.
    expect(portfolioSource).not.toContain('<Reveal');
    // Settings used to fade its reading column in on its own timing.
    expect(settingsSource).not.toContain('motion.main');
  });

  it('leaves the front door assembling itself rather than fading in as a block', () => {
    expect(homeSource).toContain('<Reveal');
    expect(homeSource).not.toContain('page-transition-enter');
  });

  it('keeps the shared entrance honouring reduced motion', () => {
    const block = appCss.slice(appCss.indexOf('@media (prefers-reduced-motion: reduce)'));
    expect(block).toContain('.page-transition-enter');
    expect(block).toContain('animation: none !important;');
  });
});
