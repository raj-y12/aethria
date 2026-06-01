import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import {
  getLoginEntryTransition,
  LOGIN_ENTRY_SESSION_KEY,
} from '../src/lib/loginEntryTransition.ts';

assert.equal(LOGIN_ENTRY_SESSION_KEY, 'aethria_just_logged_in');
assert.deepEqual(getLoginEntryTransition(false), {
  contentExitMs: 140,
  appRevealMs: 180,
  navigateDelayMs: 140,
});
assert.deepEqual(getLoginEntryTransition(true), {
  contentExitMs: 0,
  appRevealMs: 80,
  navigateDelayMs: 0,
});

const loginPage = readFileSync(resolve(import.meta.dirname, '../src/components/LoginPage.tsx'), 'utf8');
assert.equal(loginPage.includes('window.location.replace'), false);
assert.equal(loginPage.includes('clipPath'), false);
assert.equal(loginPage.includes("filter: 'blur"), false);
assert.equal(loginPage.includes("navigate('/v1'"), true);

console.log('login entry transition tests passed');
