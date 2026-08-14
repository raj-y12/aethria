import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const rootDir = path.dirname(fileURLToPath(import.meta.url));

/**
 * Public demo build — `vite build --config vite.demo.config.ts`.
 *
 * Same stubbing as the screenshot harness (Clerk aliased away, mock API), but
 * built for hosting rather than capture: emitted to `dist/demo` so the app
 * deployment serves it at /demo, which aethria.co/demo rewrites to.
 *
 * `emptyOutDir: false` matters — this runs after the main app build and must
 * not wipe `dist`.
 */
export default defineConfig({
  plugins: [react()],
  root: path.resolve(rootDir, 'demo'),
  base: '/demo/',
  resolve: {
    alias: {
      '@aethria/product-chrome': path.resolve(rootDir, '../packages/product-chrome/src/index.ts'),
      '@clerk/react-router': path.resolve(rootDir, 'screenshot/clerk-stub.ts'),
      '@clerk/react': path.resolve(rootDir, 'screenshot/clerk-stub.ts'),
    },
  },
  build: {
    outDir: path.resolve(rootDir, 'dist/demo'),
    emptyOutDir: false,
  },
  server: { port: 5182, strictPort: true },
});
