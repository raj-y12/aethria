import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/react';
import { afterEach } from 'vitest';

// React Testing Library: unmount and clean up the DOM after each test so tests
// stay isolated.
afterEach(() => {
  cleanup();
});
