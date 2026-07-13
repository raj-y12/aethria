import { describe, expect, it } from 'vitest';
import appSource from '../../App.tsx?raw';
import operationsSource from '../OperationsStrip.tsx?raw';
import source from '../SettingsPage.tsx?raw';

describe('Settings focused-mode layout contract', () => {
  it('dissolves the app spine like the front door (bare chrome)', () => {
    // The chrome decision must NOT force Settings to 'full'; it joins the
    // bare/takeover surfaces alongside the front door.
    expect(appSource).toContain("chrome={!isPortfolioRoute && !isFundRoute && !isFlowRoute ? 'bare' : 'full'}");
    expect(appSource).not.toContain("!isSettingsRoute && !isPortfolioRoute");
  });

  it('is a top bar + navigation rail over one scrolling reading column', () => {
    expect(source).toContain('<SettingsTopBar');
    expect(source).toContain('<SettingsRail');
    expect(source).toContain('ref={contentScrollRef}');
    expect(source).toContain('overscroll-contain bg-paper');
  });

  it('replaces tabs with a scroll-spy of stacked sections', () => {
    expect(source).toContain('IntersectionObserver');
    expect(source).toContain("divide-y divide-oxford/[0.06]");
    expect(source).not.toContain("role=\"tablist\"");
    expect(source).not.toContain('activeTab');
    expect(source).not.toContain('lg:grid-cols-[minmax(0,61.8fr)_minmax(0,38.2fr)]');
  });

  it('keeps every configuration section in the single column', () => {
    expect(source).toContain('The mandate');
    expect(source).toContain('Decision mechanics');
    expect(source).toContain('Scoring weights');
    expect(source).toContain('Memo output');
    expect(source).toContain('Ruling workflow');
    expect(source).toContain('Cost budget');
    expect(source).toContain('System state');
    expect(source).not.toContain('function SettingsSection');
  });

  it('does not hijack the spine — it removes it', () => {
    expect(source).not.toContain('setSpineOverride');
    expect(source).not.toContain('SpineNavButton');
  });

  it('keeps the rounded switch language', () => {
    expect(source).toContain('rounded-full');
    expect(operationsSource).toContain('rounded-full');
  });
});
