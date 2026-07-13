import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

const source = readFileSync(resolve(process.cwd(), 'src/settings/SettingsPage.tsx'), 'utf8');

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
});
