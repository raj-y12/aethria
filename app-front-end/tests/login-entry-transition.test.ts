import { describe, it } from 'vitest';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import {
  getLoginEntryTransition,
  LOGIN_ENTRY_SESSION_KEY,
} from '../src/lib/loginEntryTransition.ts';

describe('login entry transition', () => {
  it('exposes the session key and motion timings', () => {
    assert.equal(LOGIN_ENTRY_SESSION_KEY, 'aethria_just_logged_in');
    // Navigate only once the sign-in content has finished fading.
    assert.deepEqual(getLoginEntryTransition(false), {
      contentExitMs: 180,
      navigateDelayMs: 180,
    });
    assert.deepEqual(getLoginEntryTransition(true), {
      contentExitMs: 0,
      navigateDelayMs: 0,
    });
  });

  it('keeps the LoginPage + App handoff invariants in source', () => {
    const loginPage = readFileSync(resolve(import.meta.dirname, '../src/components/LoginPage.tsx'), 'utf8');
    assert.equal(loginPage.includes('window.location.replace'), false);
    assert.equal(loginPage.includes('clipPath'), false);
    assert.equal(loginPage.includes("filter: 'blur"), false);
    assert.equal(loginPage.includes('y: -12'), true);
    assert.equal(loginPage.includes("navigate('/v1'"), true);

    const app = readFileSync(resolve(import.meta.dirname, '../src/App.tsx'), 'utf8');
    assert.equal(app.includes('hasLoginEntryHandoff'), true);
    assert.equal(app.includes('!tokenReady && !hasLoginEntryHandoff'), true);
    // The atmosphere and bracket frame are already on screen at the hand-off;
    // the shell must not fade or slide them (only Home's content reveals).
    assert.equal(app.includes('y: 16'), false);
  });
});
