/// <reference types="vitest/config" />
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const rootDir = path.dirname(fileURLToPath(import.meta.url))

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@aethria/product-chrome': path.resolve(rootDir, '../packages/product-chrome/src/index.ts'),
    },
  },
  build: {
    rollupOptions: {
      output: {
        // Split large, stable vendors into their own chunks for better cross-deploy
        // caching and a smaller initial app chunk. Heavy libs that are *dynamically*
        // imported (jspdf, html2canvas) are deliberately left untouched so they stay
        // as lazy async chunks — routing them here would eagerly bundle them.
        manualChunks(id) {
          if (!id.includes('node_modules')) return;
          if (id.includes('jspdf') || id.includes('html2canvas')) return;
          if (id.includes('@clerk')) return 'vendor-clerk';
          if (id.includes('@tanstack')) return 'vendor-tanstack';
          if (
            id.includes('framer-motion') ||
            id.includes('motion-dom') ||
            id.includes('motion-utils')
          )
            return 'vendor-motion';
          if (
            id.includes('react-router') ||
            id.includes('react-dom') ||
            id.includes('/react/') ||
            id.includes('/scheduler/')
          )
            return 'vendor-react';
          return;
        },
      },
    },
  },
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    // Playwright e2e specs live under e2e/ and run via `npm run test:e2e`,
    // not the Vitest unit runner.
    exclude: ['node_modules', 'dist', 'e2e/**'],
    css: false,
  },
})
