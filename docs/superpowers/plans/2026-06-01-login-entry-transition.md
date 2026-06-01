# Login Entry Transition Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the abrupt hard reload after `Enter Aethria` with a smooth in-app transition into `/v1`.

**Architecture:** Keep the behavior inside the existing React Router and Framer Motion stack. Add a small transition helper for timing, make `LoginPage` exit with the same `opacity + y` motion used by the sign-in page, preserve the handoff through the token-ready gate, and let `AppShell` enter with matching `opacity + y` motion.

**Tech Stack:** React, React Router, Framer Motion, existing `usePrefersReducedMotion`, Node assertion tests.

---

### Task 1: Regression Guard

**Files:**
- Create: `app-front-end/tests/login-entry-transition.test.ts`
- Modify later: `app-front-end/src/lib/loginEntryTransition.ts`
- Modify later: `app-front-end/src/components/LoginPage.tsx`

- [ ] **Step 1: Write the failing test**

```ts
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import {
  getLoginEntryTransition,
  LOGIN_ENTRY_SESSION_KEY,
} from '../src/lib/loginEntryTransition.ts';

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

console.log('login entry transition tests passed');
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node --experimental-strip-types app-front-end/tests/login-entry-transition.test.ts`

Expected: FAIL because `src/lib/loginEntryTransition.ts` does not exist yet.

### Task 2: Transition Helper

**Files:**
- Create: `app-front-end/src/lib/loginEntryTransition.ts`

- [ ] **Step 1: Implement minimal helper**

```ts
export const LOGIN_ENTRY_SESSION_KEY = 'aethria_just_logged_in';

export type LoginEntryTransition = {
  contentExitMs: number;
  appRevealMs: number;
  navigateDelayMs: number;
};

export function getLoginEntryTransition(reduceMotion: boolean): LoginEntryTransition {
  return reduceMotion
    ? { contentExitMs: 0, appRevealMs: 80, navigateDelayMs: 0 }
    : { contentExitMs: 280, appRevealMs: 550, navigateDelayMs: 260 };
}
```

- [ ] **Step 2: Run test to verify the helper passes and component guard still fails**

Run: `node --experimental-strip-types app-front-end/tests/login-entry-transition.test.ts`

Expected: FAIL because `LoginPage.tsx` still contains `window.location.replace`.

### Task 3: Login Exit Transition

**Files:**
- Modify: `app-front-end/src/components/LoginPage.tsx`

- [ ] **Step 1: Replace hard redirect with animated in-app navigation**

Use `getLoginEntryTransition(reduceMotion)` in `handleEnterSystem`. Set the existing session key, enter a short `entering` state, and call `navigate('/v1', { replace: true })` after `navigateDelayMs`.

- [ ] **Step 2: Add sign-in-style content exit motion**

Wrap the login content in a `motion.div` that fades and moves up by 12px when entering. Do not add blur, wipes, full-screen overlays, or dramatic movement.

- [ ] **Step 3: Run test to verify it passes**

Run: `node --experimental-strip-types app-front-end/tests/login-entry-transition.test.ts`

Expected: PASS.

### Task 4: App Shell Arrival

**Files:**
- Modify: `app-front-end/src/App.tsx`

- [ ] **Step 1: Add one-time app reveal**

Read `LOGIN_ENTRY_SESSION_KEY` in `AppShell`, preserve the handoff through the token-ready route guard, and wrap the app content in a matching `opacity + y` reveal when arriving from login.

- [ ] **Step 2: Verify build**

Run: `npm run build` from `app-front-end`.

Expected: TypeScript and Vite build complete with exit code 0.
