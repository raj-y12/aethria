import { describe, it, expect } from 'vitest';

/**
 * fundConfiguration.regression.ts is a module of `throw`-on-violation invariant
 * checks that previously ran nowhere (it was imported by nothing, so the
 * assertions never executed). Importing it here executes those checks inside the
 * test runner: any violated invariant throws at module-eval time and fails this
 * test, which is exactly what the file was written to guard against.
 */
describe('fundConfiguration invariants', () => {
  it('holds all configuration invariants without throwing', async () => {
    await expect(import('../fundConfiguration.regression')).resolves.toBeDefined();
  });
});
