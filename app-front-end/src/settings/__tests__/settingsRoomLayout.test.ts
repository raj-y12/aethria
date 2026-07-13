import { describe, expect, it } from 'vitest';
import operationsSource from '../OperationsStrip.tsx?raw';
import source from '../SettingsPage.tsx?raw';

describe('Settings room layout contract', () => {
  it('uses the shared Fund room shell with fixed chrome and a scrolling body', () => {
    expect(source).toContain("import { workspaceLayout } from '../design-system/workspaceLayout'");
    expect(source).toContain('<SettingsRoomChrome');
    expect(source).toContain('className="flex-none bg-paper"');
    expect(source).toContain('ref={contentScrollRef}');
    expect(source).toContain('overscroll-contain bg-paper');
  });

  it('leaves the normal application spine intact', () => {
    expect(source).not.toContain('setSpineOverride');
    expect(source).not.toContain('SpineNavButton');
    expect(source).not.toContain('spineActionsRef');
  });

  it('composes Decision and Administration like Fund room panels', () => {
    expect(source).toContain('lg:grid-cols-[minmax(0,61.8fr)_minmax(0,38.2fr)]');
    expect(source).toContain('The mandate');
    expect(source).toContain('Decision mechanics');
    expect(source).toContain('Scoring weights');
    expect(source).toContain('Memo output');
    expect(source).toContain('Ruling workflow');
    expect(source).toContain('Cost budget');
    expect(source).toContain('System state');
    expect(source).not.toContain('function SettingsSection');
  });

  it('keeps the original rounded switch language', () => {
    expect(source).toContain('rounded-full');
    expect(operationsSource).toContain('rounded-full');
  });
});
