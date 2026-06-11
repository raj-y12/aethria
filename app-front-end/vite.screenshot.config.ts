import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const rootDir = path.dirname(fileURLToPath(import.meta.url));

/**
 * Screenshot harness config — `vite --config vite.screenshot.config.ts`.
 * Aliases Clerk to a stub so the real pages render against mock data
 * (screenshot/mock.ts) with no auth or backend. Open:
 *   /screenshot/index.html?route=/v1/flow
 */
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@aethria/product-chrome': path.resolve(rootDir, '../packages/product-chrome/src/index.ts'),
      '@clerk/react-router': path.resolve(rootDir, 'screenshot/clerk-stub.ts'),
      '@clerk/react': path.resolve(rootDir, 'screenshot/clerk-stub.ts'),
    },
  },
  server: { port: 5181, strictPort: true },
});
