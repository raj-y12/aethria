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
    assert.deepEqual(getLoginEntryTransition(false), {
      contentExitMs: 280,
      appRevealMs: 550,
      navigateDelayMs: 260,
    });
    assert.deepEqual(getLoginEntryTransition(true), {
      contentExitMs: 0,
      appRevealMs: 80,
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
    assert.equal(app.includes('y: 16'), true);
  });
});
