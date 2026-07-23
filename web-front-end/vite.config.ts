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
  server: {
    port: 3001,
  },
  // Read by vite-react-ssg. Only '/' and '/home' are prerendered (both render
  // HomePage); private routes and the gate stay client-side.
  ssgOptions: {
    entry: 'src/main.tsx',
    includedRoutes: () => ['/', '/home'],
  },
})
